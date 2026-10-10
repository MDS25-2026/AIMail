package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"html"
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
	"os/signal"
	"regexp"
	"slices"
	"sort"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"time"

	"cloud.google.com/go/pubsub"
	"github.com/joho/godotenv"
	"google.golang.org/api/gmail/v1"
	"google.golang.org/api/option"
)

// Supabase config — read from env, never hardcode keys.
// Expects SUPABASE_URL (e.g. https://xxxx.supabase.co) and
// SUPABASE_SERVICE_KEY (service_role key, kept server-side only).
// Assigned in main() after the .env load, not at package init (which runs too early).
var (
	supabaseURL string
	supabaseKey string
)

// #86: http.DefaultClient has no deadline, so a hung PostgREST connection blocked the receive
// callback forever. DNS here resolves through Tailscale, which makes that a routine failure
// rather than a theoretical one.
var supabaseClient = &http.Client{Timeout: supabaseTimeout()}

func supabaseTimeout() time.Duration {
	seconds, err := strconv.Atoi(getEnvOrDefault("SUPABASE_TIMEOUT_SECONDS", "10"))
	if err != nil || seconds <= 0 {
		return 10 * time.Second
	}
	return time.Duration(seconds) * time.Second
}

// --- PII masking -----------------------------------------------------------
//
// Format-clear PII (email, phone, Malaysian IC) is redacted here by deterministic, ordered
// regex — most-specific first, so an IC is masked before the phone pattern can see its
// digits. Context-dependent PII (names, locations, orgs, account numbers) is left to
// Presidio's NER below. Splitting by PII *nature* rather than by tool is what removes the
// "different-length numbers, wrong type" mis-tagging: no two patterns fight over one span.

var (
	emailRegex = regexp.MustCompile(`[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}`)
	// Malaysian IC: dashed YYMMDD-PB-###G is unambiguous; a bare 12-digit run counts as an IC
	// only if its YYMMDD prefix is a plausible date (isICDate) — that separates it from a
	// 12-digit account/order number by structure, not just length.
	// Separator is dash or space: forms typed by hand carry "880101 14 5523" as often as dashes.
	icDashedRegex = regexp.MustCompile(`\b\d{6}[-\s]\d{2}[-\s]\d{4}\b`)
	icBareRegex   = regexp.MustCompile(`\b\d{12}\b`)
	// Three branches: Malaysian (+60/0 prefix), US parenthesized "(713) 853-6161", and US
	// separated "713-853-6161". Runs AFTER the IC pass, so a 12-digit IC is already redacted.
	// The US branches require parens or separators, so they can't swallow a bare account digit-run.
	// MY branch allows a separator and parens after the country code ("+60 (12) 345 6789").
	// The final branch is a short local number ("555-0142"): separator required, so it cannot
	// swallow a bare digit run, and it runs after the IC pass so an IC is already redacted.
	// International numbers outside Malaysia ("+65 9123 4567", "+44 20 7946 0958"): a "+" and a
	// country code, then two to five digit groups. Runs after the Malaysian branch.
	intlPhoneRegex = regexp.MustCompile(`\+[1-9]\d{0,2}[\s.-]?\(?\d{1,4}\)?(?:[\s.-]?\d{2,5}){1,4}`)
	// Passports: one or two capitals then seven or eight digits ("A12345678"). The digits-only
	// account pattern can never match after a letter, so this sits in the floor.
	passportRegex = regexp.MustCompile(`\b[A-Z]{1,2}\d{7,8}\b`)
	// Links: the query and fragment carry reset tokens and encoded addresses; only the host is
	// needed, by the agent's phishing check.
	urlRegex   = regexp.MustCompile(`https?://[^\s<>"')\]]+`)
	phoneRegex = regexp.MustCompile(`(?:\+?60|\b0)[\s.-]?\(?\d{1,2}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}\b|\(\d{3}\)[\s.-]?\d{3}[\s.-]?\d{4}|\b\d{3}[\s.-]\d{3}[\s.-]\d{4}\b|\b\d{3}[.-]\d{4}\b`)
)

// isICDate reports whether the YYMMDD prefix of a bare 12-digit string is a plausible date,
// i.e. the run really looks like a Malaysian IC and not an arbitrary 12-digit number.
func isICDate(twelveDigits string) bool {
	if len(twelveDigits) != 12 { // invariant: only called on a \d{12} match, but never index blindly
		return false
	}
	month, _ := strconv.Atoi(twelveDigits[2:4])
	day, _ := strconv.Atoi(twelveDigits[4:6])
	return month >= 1 && month <= 12 && day >= 1 && day <= 31
}

// maskPII replaces format-clear PII by ordered regex (email -> IC -> passport -> phone) with
// numbered placeholders from v, and returns the masked text plus email/phone counts for the audit
// log. IC is masked too (over-masking is preferred) but not separately counted — the persisted
// metric tracks the 80% email/phone floor.
func maskPII(text string, v *detailVault) (masked string, emailsMasked, phonesMasked int) {
	as := func(kind detailKind) func(string) string {
		return func(value string) string { return v.placeholder(kind, value) }
	}
	masked = urlRegex.ReplaceAllStringFunc(text, withoutQuery)
	masked = emailRegex.ReplaceAllStringFunc(masked, func(value string) string {
		emailsMasked++
		return v.placeholder(kindEmail, value)
	})
	masked = icDashedRegex.ReplaceAllStringFunc(masked, as(kindIC))
	masked = icBareRegex.ReplaceAllStringFunc(masked, func(value string) string {
		if isICDate(value) {
			return v.placeholder(kindIC, value)
		}
		return value
	})
	masked = passportRegex.ReplaceAllStringFunc(masked, as(kindPassport))
	countPhone := func(value string) string {
		phonesMasked++
		return v.placeholder(kindPhone, value)
	}
	masked = phoneRegex.ReplaceAllStringFunc(masked, countPhone)
	masked = intlPhoneRegex.ReplaceAllStringFunc(masked, countPhone)
	return masked, emailsMasked, phonesMasked
}

// withoutQuery keeps a link's scheme, host and path. An unparseable link is cut at the first
// "?" or "#" instead, so a token never survives a parse error.
func withoutQuery(link string) string {
	parsed, err := url.Parse(link)
	if err != nil {
		if cut := strings.IndexAny(link, "?#"); cut >= 0 {
			return link[:cut]
		}
		return link
	}
	parsed.RawQuery, parsed.Fragment, parsed.RawFragment = "", "", ""
	return parsed.String()
}

// --- Presidio NER masking (layered on top of the regex floor) ---------------
//
// Presidio (the analyzer container) catches context-dependent PII the
// regex can't — names, locations, organizations, and account numbers (identifiable only by
// nearby words). It runs AFTER maskPII on the already-floored text, so the email/phone/IC
// floor holds even when the containers are down: any Presidio error degrades to the regex
// result, and raw text is never stored.

// presidioClient bounds each call so a hung container can't block the webhook handler.
// Package-level (not http.DefaultClient) to avoid mutating shared global client state.
var presidioClient = &http.Client{Timeout: 5 * time.Second}

type presidioPattern struct {
	Name  string  `json:"name"`
	Regex string  `json:"regex"`
	Score float64 `json:"score"`
}

type presidioRecognizer struct {
	Name              string            `json:"name"`
	SupportedLanguage string            `json:"supported_language"`
	SupportedEntity   string            `json:"supported_entity"`
	Patterns          []presidioPattern `json:"patterns"`
	Context           []string          `json:"context,omitempty"`
}

type presidioAnalyzeRequest struct {
	Text             string               `json:"text"`
	Language         string               `json:"language"`
	ScoreThreshold   float64              `json:"score_threshold"`
	Entities         []string             `json:"entities,omitempty"`
	AdHocRecognizers []presidioRecognizer `json:"ad_hoc_recognizers,omitempty"`
}

type presidioResult struct {
	EntityType string  `json:"entity_type"`
	Start      int     `json:"start"`
	End        int     `json:"end"`
	Score      float64 `json:"score"`
}

// localeRecognizers holds only the context-gated account recogniser. IC and phone moved to the
// regex floor (their formats are fixed) — leaving them here made Presidio score-fight the built-in
// PHONE_NUMBER recogniser and mis-type numbers by length. Account numbers stay because a bare
// digit-run is identifiable only by nearby words, which is exactly Presidio's context feature.
var localeRecognizers = []presidioRecognizer{
	{
		Name:              "FLEXIBLE_ACCOUNT_RECOGNIZER",
		SupportedLanguage: "en",
		SupportedEntity:   "ACCOUNT_NUMBER",
		// From 4 digits: real emails cite a partial account ("the account ending 4471"). The
		// 0.4 base still sits below the 0.6 threshold, so a bare 4-digit run like a year is only
		// masked when a context word below sits near it.
		// Grouped as banks print them ("5141 2345 6789", "1234-5678-90"): three groups at least, so an amount
		// ("150 000") is not one, and never an ISO date. The IC and phone floor has already replaced its shapes.
		Patterns: []presidioPattern{
			{Name: "arbitrary_digit_pattern", Regex: `\b\d{4,16}\b`, Score: 0.4},
			{Name: "grouped_digit_pattern", Regex: `\b(?!\d{4}-\d{2}-\d{2}\b)\d{3,6}(?:[ -]\d{2,6}){2,3}\b`, Score: 0.4},
		},
		Context: []string{"account", "acc", "akaun", "bank", "maybank", "cimb", "rhb", "public bank", "transfer", "reference", "ref", "passport", "policy", "member", "employee", "emp", "staff", "badge", "payroll"},
	},
	{
		Name:              "MY_POSTCODE_RECOGNIZER",
		SupportedLanguage: "en",
		SupportedEntity:   "MY_POSTCODE",
		// Five digits are an amount or an order number as often as a postcode: only address words make it one.
		// No state names: "our Selangor branch sold 12000 units" is business context (see allowedLocations).
		Patterns: []presidioPattern{{Name: "my_postcode", Regex: `\b\d{5}\b`, Score: 0.4}},
		Context:  []string{"jalan", "jln", "taman", "tmn", "lorong", "persiaran", "lebuh", "bandar", "kampung", "kg", "address", "alamat", "postcode", "poskod", "kuala", "petaling", "pulau"},
	},
	{
		Name:              "MY_VEHICLE_PLATE_RECOGNIZER",
		SupportedLanguage: "en",
		SupportedEntity:   "VEHICLE_PLATE",
		// "WXY 1234", "VAB 123 A". Presidio matches case-blind and its context words as substrings, so the
		// letters are forced uppercase, URL and word fragments are ruled out, and "car"/"plat" (card, platform) are not context.
		Patterns: []presidioPattern{{Name: "my_plate", Regex: `(?<![\w/.:=-])(?-i:[A-Z]{1,3} ?\d{1,4}(?: ?[A-Z])?)(?![\w/-])`, Score: 0.4}},
		Context:  []string{"plate", "kereta", "vehicle", "kenderaan", "jpj", "motorcycle", "motosikal", "lorry"},
	},
}

// allowedLocations are place names kept in the text rather than redacted. A country or state in
// business mail is organisational context, not personal data: masking "the US desk" or "our
// Selangor branch" strips meaning from the draft the model then writes, without protecting
// anyone. The boundary is country and state only — cities, districts and streets stay masked, so
// anything ambiguous errs toward redaction. Keep this list short; extending it to cities would
// punch holes in the privacy claim. Recorded in docs/decisions/lane-a-spine.md.
var allowedLocations = map[string]bool{
	"us": true, "u.s.": true, "u.s.a.": true, "usa": true, "america": true,
	"uk": true, "u.k.": true, "britain": true, "eu": true, "apac": true, "asean": true,
	"malaysia": true, "singapore": true, "indonesia": true, "thailand": true,
	"australia": true, "india": true, "china": true, "japan": true,
	// Malaysian states — "our Selangor branch" is a business unit, not a person's address.
	"selangor": true, "penang": true, "johor": true, "sabah": true, "sarawak": true,
	"melaka": true, "malacca": true, "perak": true, "pahang": true, "kedah": true,
	"kelantan": true, "terengganu": true, "perlis": true, "negeri sembilan": true,
}

// filterAllowedLocations drops LOCATION hits naming a country or state, leaving every other
// entity untouched. Offsets from Presidio are Python character indices, so the text is sliced as
// runes — byte slicing would misalign the moment an email contains a non-ASCII character.
func filterAllowedLocations(text string, results []presidioResult) []presidioResult {
	runes := []rune(text)
	kept := make([]presidioResult, 0, len(results))
	for _, r := range results {
		if r.EntityType == "LOCATION" && r.Start >= 0 && r.End <= len(runes) && r.Start < r.End {
			if allowedLocations[strings.ToLower(strings.TrimSpace(string(runes[r.Start:r.End])))] {
				continue
			}
		}
		kept = append(kept, r)
	}
	return kept
}

// maskText applies the regex PII floor first (always, offline-proof), then layers Presidio
// NER on the floored text. On any Presidio error it degrades to the regex result — raw text
// is never returned. emails/phones counts come from the regex pass so they stay honest in
// both modes; degraded reports whether Presidio ran, for the audit log.
// maskText runs the regex floor over the whole text, then NER over it in pieces. The floor is never
// chunked: an email address cut across two pieces would match in neither. NER is, because one
// Presidio call on a long body or a 20-page PDF can outrun presidioClient's timeout.
func maskText(ctx context.Context, text string, v *detailVault) (masked string, emailsMasked, phonesMasked int, degraded bool) {
	masked, emailsMasked, phonesMasked = maskPII(text, v)
	var pieces []string
	for _, chunk := range chunkText(masked, nerChunkChars) {
		piece, err := maskWithPresidio(ctx, chunk, v)
		if err != nil {
			log.Printf("presidio degraded, regex-only for this field: %v", err)
			return masked, emailsMasked, phonesMasked, true
		}
		pieces = append(pieces, piece)
	}
	return strings.Join(pieces, ""), emailsMasked, phonesMasked, false
}

// maskWithPresidio detects PII with the analyzer container and replaces each entity with a
// numbered placeholder from v. Replacement happens here rather than in the anonymizer container so
// the value behind every placeholder is known and can be sealed into the vault. Any error is
// returned so the caller can degrade to the regex floor.
func maskWithPresidio(ctx context.Context, text string, v *detailVault) (string, error) {
	if strings.TrimSpace(text) == "" {
		return text, nil
	}
	analyzerURL := getEnvOrDefault("PRESIDIO_ANALYZER_URL", "http://localhost:5001/analyze")
	analyzePayload, err := json.Marshal(presidioAnalyzeRequest{
		Text:           text,
		Language:       "en",
		ScoreThreshold: 0.6,
		// CREDIT_CARD and IBAN_CODE are Presidio built-ins that validate their checksums, so they
		// cannot fire on an invoice or order number that merely looks card- or IBAN-shaped. SWIFT/BIC
		// is left out on purpose: it names a bank, which is public, not a person.
		Entities:         []string{"PERSON", "LOCATION", "ORGANIZATION", "ACCOUNT_NUMBER", "CREDIT_CARD", "IBAN_CODE", "PHONE_NUMBER", "EMAIL_ADDRESS", "MY_POSTCODE", "VEHICLE_PLATE"},
		AdHocRecognizers: localeRecognizers,
	})
	if err != nil {
		return "", fmt.Errorf("marshal analyze request: %w", err)
	}
	raw, err := presidioPost(ctx, analyzerURL, analyzePayload)
	if err != nil {
		return "", fmt.Errorf("presidio analyzer: %w", err)
	}
	var results []presidioResult
	if err := json.Unmarshal(raw, &results); err != nil {
		return "", fmt.Errorf("decode analyze results: %w", err)
	}
	return replaceEntities(text, filterAllowedLocations(text, results), v), nil
}

// entityKinds maps Presidio's entity names to placeholder kinds. An unlisted entity is still
// masked, as an account-like identifier.
var entityKinds = map[string]detailKind{
	"PERSON": kindPerson, "LOCATION": kindLocation, "ORGANIZATION": kindOrg,
	"ACCOUNT_NUMBER": kindAccount, "IBAN_CODE": kindAccount, "CREDIT_CARD": kindCard,
	// A plate needs no kind of its own: it is an identifier like an account, and every service already knows ACCOUNT.
	"MY_POSTCODE": kindLocation, "VEHICLE_PLATE": kindAccount,
	"PHONE_NUMBER": kindPhone, "EMAIL_ADDRESS": kindEmail,
}

func entityKind(entity string) detailKind {
	if kind, ok := entityKinds[entity]; ok {
		return kind
	}
	return kindAccount
}

// replaceEntities swaps each detected entity for its placeholder. Offsets are Python character
// indices, so the text is handled as runes. Where entities overlap the longest wins, and anything
// touching a placeholder the regex floor already wrote is left alone.
func replaceEntities(text string, results []presidioResult, v *detailVault) string {
	runes := []rune(text)
	taken := runeSpans(text, placeholderRegex.FindAllStringIndex(text, -1))
	sort.SliceStable(results, func(i, j int) bool {
		li, lj := results[i].End-results[i].Start, results[j].End-results[j].Start
		return li > lj || (li == lj && results[i].Score > results[j].Score)
	})
	var chosen []presidioResult
	for _, r := range results {
		if r.Start < 0 || r.End > len(runes) || r.Start >= r.End || overlapsAny(r.Start, r.End, taken) {
			continue
		}
		taken = append(taken, [2]int{r.Start, r.End})
		chosen = append(chosen, r)
	}
	// Numbered in reading order, then replaced from the end so earlier offsets stay valid.
	sort.Slice(chosen, func(i, j int) bool { return chosen[i].Start < chosen[j].Start })
	tokens := make([][]rune, len(chosen))
	for i, r := range chosen {
		tokens[i] = []rune(v.placeholder(entityKind(r.EntityType), string(runes[r.Start:r.End])))
	}
	for i := len(chosen) - 1; i >= 0; i-- {
		r := chosen[i]
		runes = append(runes[:r.Start], append(tokens[i], runes[r.End:]...)...)
	}
	return string(runes)
}

func overlapsAny(start, end int, spans [][2]int) bool {
	for _, s := range spans {
		if start < s[1] && s[0] < end {
			return true
		}
	}
	return false
}

// presidioPost POSTs a JSON payload to a Presidio endpoint and returns the raw response body.
func presidioPost(ctx context.Context, url string, payload []byte) ([]byte, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(payload))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := presidioClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		return nil, fmt.Errorf("status %d", resp.StatusCode)
	}
	return io.ReadAll(resp.Body)
}

func getEnvOrDefault(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

// --- Supabase storage + audit log -------------------------------------------

// MaskedContent is every content column, all of it masked. It is written whole or not at all:
// a quarantined row has none of it, and completing that row later patches exactly these fields.
type MaskedContent struct {
	Subject       string `json:"subject"`
	BodyMasked    string `json:"body_masked"`
	SnippetMasked string `json:"snippet_masked"`
	EmailsMasked  int    `json:"emails_masked"`
	PhonesMasked  int    `json:"phones_masked"`
	MaskingStatus string `json:"masking_status"`
	// The sealed placeholder-to-value map (details.go), as PostgREST's `\x` hex; omitted when empty.
	PiiVault string `json:"pii_vault,omitempty"`
}

// StoredMessage is what we persist for each processed email, post-masking.
type StoredMessage struct {
	UserID         string      `json:"user_id,omitempty"` // the mailbox owner; omitted (NULL) for token.json
	GmailMessageID string      `json:"gmail_message_id"`
	SlaPriority    SLAPriority `json:"sla_priority,omitempty"` // deterministic pre-AI priority; empty means let AI decide
	SenderFacts
	MaskedContent
}

// QuarantinedMessage is the row for a message whose masking could not complete (#109): enough to
// show it exists and to finish it later, and no content at all.
type QuarantinedMessage struct {
	UserID         string `json:"user_id,omitempty"`
	GmailMessageID string `json:"gmail_message_id"`
	MaskingStatus  string `json:"masking_status"`
	SenderFacts
}

// supabaseInsert POSTs a row to a Supabase table via the PostgREST API. When onConflict names a
// column, a row colliding on it is ignored rather than erroring — so repeat Gmail notifications for
// the same message don't duplicate or fail. Pass "" for a plain insert.
func supabaseInsert(ctx context.Context, table string, row interface{}, onConflict string) error {
	if supabaseURL == "" || supabaseKey == "" {
		return fmt.Errorf("SUPABASE_URL / SUPABASE_SERVICE_KEY not set")
	}

	body, err := json.Marshal(row)
	if err != nil {
		return fmt.Errorf("marshal row: %w", err)
	}

	url := fmt.Sprintf("%s/rest/v1/%s", supabaseURL, table)
	prefer := "return=minimal"
	if onConflict != "" {
		url += "?on_conflict=" + onConflict
		prefer += ",resolution=ignore-duplicates"
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("build request: %w", err)
	}
	req.Header.Set("apikey", supabaseKey)
	req.Header.Set("Authorization", "Bearer "+supabaseKey)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Prefer", prefer)

	resp, err := supabaseClient.Do(req)
	if err != nil {
		return fmt.Errorf("do request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 300 {
		return fmt.Errorf("supabase insert into %s failed: status %d", table, resp.StatusCode)
	}
	return nil
}

// startTokenFileMailbox watches the original token.json mailbox, unless its account has connected
// with Google, in which case that connection already serves it. A failure is logged, not fatal:
// every connected user's mailbox still works without it.
func startTokenFileMailbox(ctx context.Context, srv *gmail.Service) {
	profile, err := srv.Users.GetProfile("me").Context(ctx).Do()
	if err != nil {
		log.Printf("token.json mailbox not started: %v", err)
		writeAuditLog(ctx, "", actionSetupWatch, auditFields{fieldStage: stageProfile, fieldErrorKind: errorKind(err)}, false)
		return
	}
	if existing := lookupMailbox(profile.EmailAddress); existing != nil {
		log.Printf("token.json mailbox is connected as user %s; using the connection", existing.ownerID)
		return
	}
	mb := &mailbox{email: strings.ToLower(profile.EmailAddress), srv: srv}
	if err := watchMailbox(ctx, mb); err != nil {
		log.Printf("token.json mailbox not started: %v", err)
		writeAuditLog(ctx, "", actionSetupWatch, auditFields{fieldStage: stageWatch, fieldErrorKind: errorKind(err)}, false)
		return
	}
	registerMailbox(mb)
	writeAuditLog(ctx, "", actionSetupWatch, nil, true)
}

// Gmail expires a watch after roughly seven days. #83: nothing renewed it, so a listener left
// running for a week stopped receiving mail with no error and no log line — restarting masked it
// during development, which is why it went unnoticed.
const watchRenewInterval = 24 * time.Hour

func renewWatchPeriodically(ctx context.Context) {
	ticker := time.NewTicker(watchRenewInterval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			for _, mb := range allMailboxes() {
				renewWatch(ctx, mb)
			}
		}
	}
}

func renewWatch(ctx context.Context, mb *mailbox) {
	if err := watchMailbox(ctx, mb); err != nil {
		// Loud on purpose: a silent renewal failure is the original bug wearing a hat.
		log.Printf("WATCH RENEWAL FAILED for user %q: %v — this mailbox stops receiving mail when the current watch expires",
			mb.ownerID, err)
		writeAuditLog(ctx, mb.ownerID, actionRenewWatch, auditFields{fieldStage: stageWatch, fieldErrorKind: errorKind(err)}, false)
		noteRefusedGrant(ctx, mb.ownerID, err)
		return
	}
	writeAuditLog(ctx, mb.ownerID, actionRenewWatch, nil, true)
}

// listenToPubSub receives until ctx is cancelled. It authenticates as the token.json account while
// one exists, else with Application Default Credentials (pubsubOptions).
func listenToPubSub(ctx context.Context, cfg pubsubConfig, opts []option.ClientOption) {
	client, err := pubsub.NewClient(ctx, cfg.projectID, opts...)
	if err != nil {
		log.Fatalf("Failed to create Pub/Sub client: %v", err)
	}
	defer client.Close()

	sub := client.Subscription(cfg.subscriptionID)
	fmt.Println("Listening for incoming emails on Pub/Sub...")

	err = sub.Receive(ctx, func(ctx context.Context, msg *pubsub.Message) {
		markReceived()
		var payload struct {
			EmailAddress string `json:"emailAddress"`
			HistoryID    uint64 `json:"historyId"`
		}
		if err := json.Unmarshal(msg.Data, &payload); err != nil {
			// Unparseable payload will never parse on redelivery, so ack it rather than loop.
			log.Printf("Error unmarshalling Pub/Sub data: %v", err)
			msg.Ack()
			return
		}

		mb := lookupMailbox(payload.EmailAddress)
		if mb == nil {
			// A mailbox that disconnected, or one connected since the last sync; nothing to do
			// with it now, and redelivering would not change that.
			log.Printf("notification for a mailbox that is not connected (history %d); ignored", payload.HistoryID)
			msg.Ack()
			return
		}
		log.Printf("new mail event for user %q (history %d)", mb.ownerID, payload.HistoryID)

		// #84: acking first meant a failure during masking or storage lost the email silently,
		// with no redelivery. Acking after success risks a poison message redelivering forever,
		// so the two are separated: a message that fails repeatedly is acked and recorded rather
		// than left to loop. Pub/Sub's own delivery count is what distinguishes them.
		if err := ingestHistory(ctx, mb, payload.HistoryID); err != nil {
			if msg.DeliveryAttempt != nil && *msg.DeliveryAttempt >= maxDeliveryAttempts {
				log.Printf("GIVING UP on history %d after %d attempts: %v",
					payload.HistoryID, *msg.DeliveryAttempt, err)
				writeAuditLog(ctx, mb.ownerID, actionIngestAbandoned, auditFields{fieldHistoryID: payload.HistoryID,
					fieldAttempts: *msg.DeliveryAttempt, fieldReason: reasonTooManyAttempts, fieldErrorKind: errorKind(err)}, false)
				// Past this range, or every later notification would list it again, hit the same
				// failure first, and no newer mail would arrive until a restart.
				advanceBaseline(mb, payload.HistoryID)
				msg.Ack()
				return
			}
			if msg.DeliveryAttempt == nil {
				warnNoDeadLetter.Do(func() {
					log.Printf("WARNING: subscription %s has no dead-letter policy, so failed notifications "+
						"are retried forever; see infra/pubsub-dead-letter.md", cfg.subscriptionID)
				})
			}
			log.Printf("Ingest failed for history %d, will retry: %v", payload.HistoryID, err)
			msg.Nack()
			return
		}
		msg.Ack()
	})

	// Receive returns nil on cancellation; an error after a shutdown signal is the shutdown itself.
	if err != nil && ctx.Err() == nil {
		log.Fatalf("Error receiving Pub/Sub messages: %v", err)
	}
}

// Pub/Sub gives a history ID naming exactly what changed. #85: this used to ignore it and fetch
// whatever was newest, so two emails arriving close together both fetched the second one and the
// first was never ingested. The unique constraint on gmail_message_id hid it — the failure was a
// missing row, not a duplicate one, which is invisible unless you go looking.
const maxDeliveryAttempts = 5

// catchUpMessageCount bounds the fallback catch-up: a mailbox's newest messages, enough to cover a
// listener down for a long weekend without one notification fetching the whole inbox.
const catchUpMessageCount = 50

// Pub/Sub counts deliveries only when the subscription has a dead-letter policy; said once, not
// on every failure.
var warnNoDeadLetter sync.Once

// ingestHistory stores what a notification announced. mb.lastHistoryID is the last history ID
// successfully processed: history.list needs a starting point, and the notification's own ID is
// the *end* of the range, not the start.
func ingestHistory(ctx context.Context, mb *mailbox, historyID uint64) error {
	mb.ingesting.Lock()
	defer mb.ingesting.Unlock()
	start := atomic.LoadUint64(&mb.lastHistoryID)
	if start == 0 {
		// No baseline yet. Catch up on recent INBOX mail so nothing is dropped, then let the
		// baseline advance from here.
		advanceBaseline(mb, historyID)
		return ingestRecentInbox(ctx, mb)
	}

	call := mb.srv.Users.History.List("me").StartHistoryId(start).HistoryTypes("messageAdded").LabelId("INBOX")
	var ids []string
	err := call.Pages(ctx, func(page *gmail.ListHistoryResponse) error {
		for _, record := range page.History {
			for _, added := range record.MessagesAdded {
				if added.Message != nil {
					ids = append(ids, added.Message.Id)
				}
			}
		}
		return nil
	})
	if err != nil {
		// An expired or pruned history ID is not retryable — Gmail drops history beyond a week.
		// Fall back rather than fail the message forever.
		log.Printf("history.list from %d failed (%v); falling back to recent INBOX messages", start, err)
		writeAuditLog(ctx, mb.ownerID, actionFetchHistory, auditFields{fieldHistoryID: start,
			fieldReason: reasonHistoryUnusable, fieldErrorKind: errorKind(err)}, false)
		advanceBaseline(mb, historyID)
		return ingestRecentInbox(ctx, mb)
	}
	if err := ingestEach(ctx, mb, ids); err != nil {
		return err
	}
	// After the received mail, and never failing the notification (sent.go).
	ingestSent(ctx, mb, sentSince(ctx, mb, start))
	advanceBaseline(mb, historyID)
	return nil
}

// ingestEach stores each message in order. A permanent failure is recorded and skipped; any other
// stops the run, so the caller's retry lists the range again (stored messages are skipped then).
func ingestEach(ctx context.Context, mb *mailbox, ids []string) error {
	for _, msgID := range ids {
		err := ingestMessage(ctx, mb, msgID)
		if isPermanentIngestFailure(err) {
			// Retrying cannot help (deleted before the fetch, or a row the database refuses), and
			// failing the range would hold every newer message behind this one.
			messageRef{ownerID: mb.ownerID, msgID: msgID}.audit(ctx, actionIngestSkipped,
				auditFields{fieldReason: reasonPermanentFailure, fieldErrorKind: errorKind(err)}, false)
			continue
		}
		if err != nil {
			// The baseline stays put, so the redelivery lists this range again and retries the
			// message; the ones already stored are skipped by messageStored.
			return fmt.Errorf("message %s: %w", msgID, err)
		}
	}
	return nil
}

// isPermanentIngestFailure is a failure that will recur on every retry: the message is gone from
// Gmail, or the database refused the row itself (a 4xx, not an outage).
func isPermanentIngestFailure(err error) bool {
	return err != nil && (isGone(err) || errors.Is(err, errRowRejected))
}

// advanceBaseline moves a mailbox's baseline forward only, and saves it so a restart resumes there.
// Notifications are handled concurrently, and a slower, older one must not move the baseline back
// and make a newer range be listed twice.
func advanceBaseline(mb *mailbox, historyID uint64) {
	if !raiseBaseline(mb, historyID) {
		return
	}
	saveConnectionState(context.Background(), mb, map[string]interface{}{"history_id": historyID})
}

// raiseBaseline reports whether historyID was newer and is now the baseline.
func raiseBaseline(mb *mailbox, historyID uint64) bool {
	for {
		current := atomic.LoadUint64(&mb.lastHistoryID)
		if historyID <= current {
			return false
		}
		if atomic.CompareAndSwapUint64(&mb.lastHistoryID, current, historyID) {
			return true
		}
	}
}

// ingestRecentInbox is the fallback for when history is unusable (a first start, or a listener
// down longer than Gmail keeps history): the newest catchUpMessageCount INBOX messages, oldest
// first. Ones already stored are skipped, so only the mail missed while down is fetched.
func ingestRecentInbox(ctx context.Context, mb *mailbox) error {
	// INBOX only, matching the label the watch is registered against (setupWatch). Without it
	// this lists mail anywhere in the mailbox — including a reply the system just sent, which
	// Gmail files in the same mailbox. That made AImail ingest its own outgoing mail and
	// generate replies to itself.
	list, err := mb.srv.Users.Messages.List("me").LabelIds("INBOX").MaxResults(catchUpMessageCount).Context(ctx).Do()
	if err != nil {
		writeAuditLog(ctx, mb.ownerID, actionFetchMessage, auditFields{fieldStage: stageList, fieldErrorKind: errorKind(err)}, false)
		return fmt.Errorf("list messages: %w", err)
	}
	ids := make([]string, len(list.Messages))
	for i, m := range list.Messages {
		ids[len(ids)-1-i] = m.Id // Gmail lists newest first
	}
	return ingestEach(ctx, mb, ids)
}

// ingestMessage fetches one message by ID, masks its PII, and persists it plus an audit entry.
func ingestMessage(ctx context.Context, mb *mailbox, msgID string) error {
	// A failed lookup falls through to a normal ingest: dropping a message is worse than paying
	// for OCR twice, and the insert's on_conflict still keeps the row single.
	isStored, err := messageStored(ctx, mb.ownerID, msgID)
	if err != nil {
		log.Printf("could not check whether %s is stored, ingesting anyway: %v", msgID, err)
	}
	if isStored {
		return nil
	}

	ref := messageRef{ownerID: mb.ownerID, msgID: msgID}
	msg, err := fetchMessage(ctx, mb.srv, ref)
	if err != nil {
		return err
	}
	if msg.Payload == nil {
		// Nothing to read or mask; a nil payload must not panic the Pub/Sub callback.
		ref.audit(ctx, actionFetchMessage, auditFields{fieldReason: reasonNoPayload}, false)
		return nil
	}
	if isOwnSentReply(msg) {
		// A reply sent from AIMail lands in the same thread and history can list it; it is
		// already shown under the email it answers, so storing it would add a fake new email.
		return nil
	}
	facts := senderFacts(msg)
	content, isComplete := maskMessage(ctx, mb.srv, msg, mb.ownerID)
	if !isComplete {
		return quarantine(ctx, mb.ownerID, msgID, facts)
	}

	slaPriority := ClassifySLA(content.Subject, content.BodyMasked, time.Now().UTC())
	stored := StoredMessage{
		UserID:         mb.ownerID,
		GmailMessageID: msgID,
		SlaPriority:    slaPriority,
		SenderFacts:    facts,
		MaskedContent:  content,
	}
	isInserted, err := insertMessage(ctx, stored)
	if err != nil {
		log.Printf("could not store message %s: %v", msgID, err)
		ref.auditFailure(ctx, actionStoreMessage, stageStore, err)
		return fmt.Errorf("store message %s: %w", msgID, err)
	}
	if !isInserted {
		log.Printf("%s already stored; the insert was ignored", msgID)
		return nil
	}
	// Counts only: the sender, subject and body are never written to stdout.
	log.Printf("stored %s: %d bytes, %d emails / %d phones masked", msgID, len(content.BodyMasked),
		content.EmailsMasked, content.PhonesMasked)
	ref.audit(ctx, actionStoreMessage, auditFields{fieldEmailsMasked: content.EmailsMasked,
		fieldPhonesMasked: content.PhonesMasked}, true)
	return nil
}

// isOwnSentReply is a message the mailbox sent, not received. Mail to yourself carries both SENT
// and INBOX and is still ingested.
func isOwnSentReply(msg *gmail.Message) bool {
	return slices.Contains(msg.LabelIds, "SENT") && !slices.Contains(msg.LabelIds, "INBOX")
}

func fetchMessage(ctx context.Context, srv *gmail.Service, ref messageRef) (*gmail.Message, error) {
	msgID := ref.msgID
	msg, err := srv.Users.Messages.Get("me", msgID).Format("full").Context(ctx).Do()
	if err != nil {
		log.Printf("could not retrieve message %s: %v", msgID, err)
		ref.auditFailure(ctx, actionFetchMessage, stageFetch, err)
		return nil, fmt.Errorf("get message %s: %w", msgID, err)
	}
	return msg, nil
}

// maskMessage masks every content field. isComplete is false when NER was unavailable for any
// of them: the caller must then store nothing of the content (#109). Attachment text is masked on
// its own and dropped rather than degraded, so it never decides the outcome.
func maskMessage(ctx context.Context, srv *gmail.Service, msg *gmail.Message, ownerID string) (MaskedContent, bool) {
	// One vault for every field, so a person named in the subject and the body is one placeholder.
	v := newDetailVault()
	maskedBody, bodyEmails, bodyPhones, degradedBody := maskText(ctx, getBody(msg.Payload), v)
	// Gmail escapes the snippet as HTML (&#39;, &amp;): unescape first, or entities split names apart for NER.
	maskedSnippet, snipEmails, snipPhones, degradedSnip := maskText(ctx, html.UnescapeString(msg.Snippet), v)
	maskedSubject, subEmails, subPhones, degradedSubj := maskText(ctx, headerValue(msg.Payload.Headers, "Subject"), v)
	if degradedBody || degradedSnip || degradedSubj {
		return MaskedContent{}, false
	}
	ref := messageRef{ownerID: ownerID, msgID: msg.Id}
	attachments, attachEmails, attachPhones := maskAttachmentText(ctx, ref, ocrAttachments(ctx, srv, ref, msg.Payload), v)
	return MaskedContent{
		Subject:       maskedSubject,
		BodyMasked:    maskedBody + attachments,
		SnippetMasked: maskedSnippet,
		EmailsMasked:  bodyEmails + snipEmails + subEmails + attachEmails,
		PhonesMasked:  bodyPhones + snipPhones + subPhones + attachPhones,
		MaskingStatus: maskingComplete,
		PiiVault:      v.sealed(ownerID, msg.Id),
	}, true
}

// getBody prefers the text/html part so the dashboard can render the email like a normal inbox;
// it falls back to text/plain, then to a single-part body.
// getBody returns the message body as plain prose. text/plain is preferred over text/html
// because it needs no conversion; HTML is stripped rather than stored raw.
//
// This is a masking control, not formatting. Presidio's NER scores a name by its sentence
// context, and a name sitting immediately after markup ("<p dir=\"ltr\">Priya has...") scores
// below threshold and survives masking — the same name in prose is caught. Storing raw HTML
// silently degraded name and location recall on every HTML email, which is nearly all of them.
func getBody(part *gmail.MessagePart) string {
	if plain := collectParts(part, "text/plain"); plain != "" {
		return plain
	}
	if markup := collectParts(part, "text/html"); markup != "" {
		return htmlToText(markup)
	}
	return decodePart(part)
}

var (
	// script/style hold code, not prose: drop their contents rather than leaving CSS in the body.
	htmlDropRegex  = regexp.MustCompile(`(?is)<(script|style)[^>]*>.*?</(script|style)>`)
	htmlBreakRegex = regexp.MustCompile(`(?i)<(br\s*/?|/p|/div|/tr|/li|/h[1-6])>`)
	htmlTagRegex   = regexp.MustCompile(`<[^>]*>`)
	// A link's target is kept as text: stripping tags would otherwise erase the only sign that a
	// "verify your account" email points somewhere, which the agent's phishing check reads.
	htmlLinkRegex  = regexp.MustCompile(`(?is)<a\b[^>]*\bhref\s*=\s*["'](https?://[^"'\s]+)["'][^>]*>(.*?)</a>`)
	blankLineRegex = regexp.MustCompile(`\n{3,}`)
)

// htmlToText reduces email HTML to prose. Deliberately regex-based rather than a full parser:
// the goal is feeding clean sentences to the masker, not faithful rendering, and a parser would
// add a dependency for no gain here. Block-closing tags become newlines so sentences do not run
// together, which would confuse NER as much as the tags did.
func htmlToText(markup string) string {
	text := htmlDropRegex.ReplaceAllString(markup, " ")
	text = htmlLinkRegex.ReplaceAllString(text, "$2 ($1)")
	text = htmlBreakRegex.ReplaceAllString(text, "\n")
	text = htmlTagRegex.ReplaceAllString(text, "")
	text = html.UnescapeString(text)
	text = blankLineRegex.ReplaceAllString(text, "\n\n")
	return strings.TrimSpace(text)
}

func main() {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	loadEnvironment()
	cfg, err := loadPubSubConfig()
	if err != nil {
		log.Fatalf("listener not started: %v", err)
	}
	pubsubTopic = cfg.topicPath()
	health := startHealthServer(getEnvOrDefault(healthAddrEnv, defaultHealthAddr))
	defer stopHealthServer(health)

	// 1. Watch every connected user's mailbox, then the token.json one unless it is among them.
	legacy := legacyTokenSource(ctx)
	syncConnections(ctx)
	startLegacyMailbox(ctx, legacy)
	go syncConnectionsPeriodically(ctx)
	// #83: keep the watches alive. Gmail expires them after about a week.
	go renewWatchPeriodically(ctx)
	// #109: finish messages quarantined while Presidio was down.
	go remaskQuarantinedPeriodically(ctx)

	// 2. Receive until SIGINT or SIGTERM cancels ctx.
	listenToPubSub(ctx, cfg, pubsubOptions(legacy))
	log.Printf("listener stopped")
}

// loadEnvironment reads the shared root .env, which never overrides variables already set.
func loadEnvironment() {
	if err := godotenv.Load("../.env"); err != nil {
		log.Printf("no ../.env loaded (%v); relying on the process environment", err)
	}
	supabaseURL = os.Getenv("SUPABASE_URL")
	supabaseKey = os.Getenv("SUPABASE_SERVICE_KEY")
	if supabaseURL == "" || supabaseKey == "" {
		log.Println("WARNING: SUPABASE_URL / SUPABASE_SERVICE_KEY not set — storage and audit log writes will fail. Set these env vars before running.")
	}
}
