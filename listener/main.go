package main

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"html"
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
	"regexp"
	"strconv"
	"strings"
	"sync/atomic"
	"time"

	"cloud.google.com/go/pubsub"
	"github.com/joho/godotenv"
	"golang.org/x/oauth2"
	"golang.org/x/oauth2/google"
	"google.golang.org/api/gmail/v1"
	"google.golang.org/api/option"
)

// Configuration for GCP Pub/Sub
const (
	ProjectID      = "aimail-505405"
	TopicName      = "projects/aimail-505405/topics/gmail-notifications"
	SubscriptionID = "gmail-notifications-sub"
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

const (
	emailToken    = "[EMAIL_REDACTED]"
	phoneToken    = "[PHONE_REDACTED]"
	icToken       = "[IC_REDACTED]"
	passportToken = "[PASSPORT_REDACTED]"
)

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

// maskPII redacts format-clear PII by ordered regex (email -> IC -> phone) and returns the
// masked text plus email/phone counts for the audit log. IC is redacted too (over-masking is
// preferred) but not separately counted — the persisted metric tracks the 80% email/phone floor.
func maskPII(text string) (masked string, emailsMasked, phonesMasked int) {
	masked = urlRegex.ReplaceAllStringFunc(text, withoutQuery)
	masked = emailRegex.ReplaceAllStringFunc(masked, func(string) string {
		emailsMasked++
		return emailToken
	})
	masked = icDashedRegex.ReplaceAllString(masked, icToken)
	masked = icBareRegex.ReplaceAllStringFunc(masked, func(s string) string {
		if isICDate(s) {
			return icToken
		}
		return s
	})
	masked = passportRegex.ReplaceAllString(masked, passportToken)
	countPhone := func(string) string {
		phonesMasked++
		return phoneToken
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
// Presidio (two local containers: analyzer + anonymizer) catches context-dependent PII the
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

// presidioReplacement is the typed anonymizer config (avoids a map[string]interface{}).
type presidioReplacement struct {
	Type     string `json:"type"`
	NewValue string `json:"new_value"`
}

type presidioAnonymizeRequest struct {
	Text           string                         `json:"text"`
	AnalyzeResults []presidioResult               `json:"analyzer_results"`
	Anonymizers    map[string]presidioReplacement `json:"anonymizers,omitempty"`
}

type presidioAnonymizeResponse struct {
	Text string `json:"text"`
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
		Patterns: []presidioPattern{{Name: "arbitrary_digit_pattern", Regex: `\b\d{4,16}\b`, Score: 0.4}},
		Context:  []string{"account", "acc", "bank", "maybank", "cimb", "rhb", "public bank", "transfer", "reference", "ref", "passport", "policy", "member", "employee", "emp", "staff", "badge", "payroll"},
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
func maskText(ctx context.Context, text string) (masked string, emailsMasked, phonesMasked int, degraded bool) {
	masked, emailsMasked, phonesMasked = maskPII(text)
	var pieces []string
	for _, chunk := range chunkText(masked, nerChunkChars) {
		piece, err := maskWithPresidio(ctx, chunk)
		if err != nil {
			log.Printf("presidio degraded, regex-only for this field: %v", err)
			return masked, emailsMasked, phonesMasked, true
		}
		pieces = append(pieces, piece)
	}
	return strings.Join(pieces, ""), emailsMasked, phonesMasked, false
}

// maskWithPresidio detects PII via the analyzer container and redacts it via the anonymizer
// container. Any error is returned so the caller can degrade to the regex floor.
func maskWithPresidio(ctx context.Context, text string) (string, error) {
	if strings.TrimSpace(text) == "" {
		return text, nil
	}
	analyzerURL := getEnvOrDefault("PRESIDIO_ANALYZER_URL", "http://localhost:5001/analyze")
	anonymizerURL := getEnvOrDefault("PRESIDIO_ANONYMIZER_URL", "http://localhost:5002/anonymize")

	analyzePayload, err := json.Marshal(presidioAnalyzeRequest{
		Text:           text,
		Language:       "en",
		ScoreThreshold: 0.6,
		// CREDIT_CARD and IBAN_CODE are Presidio built-ins that validate their checksums, so they
		// cannot fire on an invoice or order number that merely looks card- or IBAN-shaped. SWIFT/BIC
		// is left out on purpose: it names a bank, which is public, not a person.
		Entities:         []string{"PERSON", "LOCATION", "ORGANIZATION", "ACCOUNT_NUMBER", "CREDIT_CARD", "IBAN_CODE", "PHONE_NUMBER", "EMAIL_ADDRESS"},
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
	results = filterAllowedLocations(text, results)
	if len(results) == 0 {
		return text, nil // no PII beyond the regex floor
	}

	anonymizePayload, err := json.Marshal(presidioAnonymizeRequest{
		Text:           text,
		AnalyzeResults: results,
		Anonymizers:    map[string]presidioReplacement{"DEFAULT": {Type: "replace", NewValue: "[Redacted]"}},
	})
	if err != nil {
		return "", fmt.Errorf("marshal anonymize request: %w", err)
	}

	raw, err = presidioPost(ctx, anonymizerURL, anonymizePayload)
	if err != nil {
		return "", fmt.Errorf("presidio anonymizer: %w", err)
	}
	var out presidioAnonymizeResponse
	if err := json.Unmarshal(raw, &out); err != nil {
		return "", fmt.Errorf("decode anonymize response: %w", err)
	}
	return out.Text, nil
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
}

// StoredMessage is what we persist for each processed email, post-masking.
type StoredMessage struct {
	GmailMessageID string    `json:"gmail_message_id"`
	FromAddr       string    `json:"from_addr"`
	ReplyTo        string    `json:"reply_to,omitempty"` // where an approved reply goes; shown to the approver
	ReceivedAt     time.Time `json:"received_at"`
	ThreadIdentity
	MaskedContent
}

// QuarantinedMessage is the row for a message whose masking could not complete (#109): enough to
// show it exists and to finish it later, and no content at all.
type QuarantinedMessage struct {
	GmailMessageID string    `json:"gmail_message_id"`
	FromAddr       string    `json:"from_addr"`
	ReplyTo        string    `json:"reply_to,omitempty"`
	ReceivedAt     time.Time `json:"received_at"`
	MaskingStatus  string    `json:"masking_status"`
	ThreadIdentity
}

// AuditLogEntry records every pipeline action for traceability — required
// for Lane A's "storage + audit log" scope.
type AuditLogEntry struct {
	Action    string    `json:"action"`
	Detail    string    `json:"detail"`
	Success   bool      `json:"success"`
	CreatedAt time.Time `json:"created_at"`
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

// writeAuditLog is a best-effort log write — failures here are logged
// locally but never block the main pipeline.
func writeAuditLog(ctx context.Context, action, detail string, success bool) {
	entry := AuditLogEntry{
		Action:    action,
		Detail:    detail,
		Success:   success,
		CreatedAt: time.Now().UTC(),
	}
	if err := supabaseInsert(ctx, "audit_log", entry, ""); err != nil {
		log.Printf("audit log write failed: %v", err)
	}
}

func getClient(config *oauth2.Config) *http.Client {
	tokFile := "token.json"
	tok, err := tokenFromFile(tokFile)
	if err != nil {
		tok = getTokenFromWeb(config)
		saveToken(tokFile, tok)
	}
	return config.Client(context.Background(), tok)
}

func getTokenFromWeb(config *oauth2.Config) *oauth2.Token {
	authURL := config.AuthCodeURL("state-token", oauth2.AccessTypeOffline)
	fmt.Printf("Go to the following link in your browser then type the authorization code: \n%v\n\nCode: ", authURL)

	var authCode string
	if _, err := fmt.Scan(&authCode); err != nil {
		log.Fatalf("Unable to read authorization code: %v", err)
	}

	tok, err := config.Exchange(context.Background(), authCode)
	if err != nil {
		log.Fatalf("Unable to retrieve token from web: %v", err)
	}
	return tok
}

func tokenFromFile(file string) (*oauth2.Token, error) {
	f, err := os.Open(file)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	tok := &oauth2.Token{}
	err = json.NewDecoder(f).Decode(tok)
	return tok, err
}

func saveToken(path string, token *oauth2.Token) {
	fmt.Printf("Saving credential file to: %s\n", path)
	f, err := os.OpenFile(path, os.O_RDWR|os.O_CREATE|os.O_TRUNC, 0600)
	if err != nil {
		log.Fatalf("Unable to cache oauth token: %v", err)
	}
	defer f.Close()
	json.NewEncoder(f).Encode(token)
}

// Registers Gmail Watch request to route mailbox changes to GCP Pub/Sub
func setupWatch(ctx context.Context, srv *gmail.Service) {
	req := &gmail.WatchRequest{
		TopicName: TopicName,
		LabelIds:  []string{"INBOX"},
	}
	res, err := srv.Users.Watch("me", req).Do()
	if err != nil {
		writeAuditLog(ctx, "setup_watch", fmt.Sprintf("watch registration failed: %v", err), false)
		log.Fatalf("Unable to set up Gmail Watch: %v", err)
	}
	fmt.Printf("Gmail Watch established! Expiration: %d, HistoryId: %d\n", res.Expiration, res.HistoryId)
	writeAuditLog(ctx, "setup_watch", fmt.Sprintf("watch established, expiration %d, historyId %d", res.Expiration, res.HistoryId), true)
	atomic.StoreUint64(&lastHistoryID, res.HistoryId)
}

// Gmail expires a watch after roughly seven days. #83: nothing renewed it, so a listener left
// running for a week stopped receiving mail with no error and no log line — restarting masked it
// during development, which is why it went unnoticed.
const watchRenewInterval = 24 * time.Hour

func renewWatchPeriodically(ctx context.Context, srv *gmail.Service) {
	ticker := time.NewTicker(watchRenewInterval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			req := &gmail.WatchRequest{TopicName: TopicName, LabelIds: []string{"INBOX"}}
			res, err := srv.Users.Watch("me", req).Do()
			if err != nil {
				// Loud on purpose: a silent renewal failure is the original bug wearing a hat.
				log.Printf("WATCH RENEWAL FAILED: %v — mail will stop arriving when the current watch expires", err)
				writeAuditLog(ctx, "renew_watch", fmt.Sprintf("renewal failed: %v", err), false)
				continue
			}
			fmt.Printf("Gmail Watch renewed. Expiration: %d, HistoryId: %d\n", res.Expiration, res.HistoryId)
			writeAuditLog(ctx, "renew_watch", fmt.Sprintf("renewed, expiration %d", res.Expiration), true)
		}
	}
}

// Listens to GCP Pub/Sub subscription using your OAuth token source
func listenToPubSub(ctx context.Context, ts oauth2.TokenSource, srv *gmail.Service) {
	client, err := pubsub.NewClient(ctx, ProjectID, option.WithTokenSource(ts))
	if err != nil {
		log.Fatalf("Failed to create Pub/Sub client: %v", err)
	}
	defer client.Close()

	sub := client.Subscription(SubscriptionID)
	fmt.Println("Listening for incoming emails on Pub/Sub...")

	err = sub.Receive(ctx, func(ctx context.Context, msg *pubsub.Message) {
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

		fmt.Printf("\nNew email event received for: %s (History ID: %d)\n", payload.EmailAddress, payload.HistoryID)

		// #84: acking first meant a failure during masking or storage lost the email silently,
		// with no redelivery. Acking after success risks a poison message redelivering forever,
		// so the two are separated: a message that fails repeatedly is acked and recorded rather
		// than left to loop. Pub/Sub's own delivery count is what distinguishes them.
		if err := ingestHistory(ctx, srv, payload.HistoryID); err != nil {
			if msg.DeliveryAttempt != nil && *msg.DeliveryAttempt >= maxDeliveryAttempts {
				log.Printf("GIVING UP on history %d after %d attempts: %v",
					payload.HistoryID, *msg.DeliveryAttempt, err)
				writeAuditLog(ctx, "ingest_abandoned",
					fmt.Sprintf("history %d abandoned after %d attempts: %v",
						payload.HistoryID, *msg.DeliveryAttempt, err), false)
				// Past this range, or every later notification would list it again, hit the same
				// failure first, and no newer mail would arrive until a restart.
				advanceBaseline(payload.HistoryID)
				msg.Ack()
				return
			}
			log.Printf("Ingest failed for history %d, will retry: %v", payload.HistoryID, err)
			msg.Nack()
			return
		}
		msg.Ack()
	})

	if err != nil {
		log.Fatalf("Error receiving Pub/Sub messages: %v", err)
	}
}

// Pub/Sub gives a history ID naming exactly what changed. #85: this used to ignore it and fetch
// whatever was newest, so two emails arriving close together both fetched the second one and the
// first was never ingested. The unique constraint on gmail_message_id hid it — the failure was a
// missing row, not a duplicate one, which is invisible unless you go looking.
const maxDeliveryAttempts = 5

// The last history ID successfully processed. history.list needs a starting point, and the
// notification's own ID is the *end* of the range, not the start.
var lastHistoryID uint64

func ingestHistory(ctx context.Context, srv *gmail.Service, historyID uint64) error {
	start := atomic.LoadUint64(&lastHistoryID)
	if start == 0 {
		// No baseline yet — first notification after startup. Fall back to the newest INBOX
		// message so nothing is dropped, then let the baseline advance from here.
		atomic.StoreUint64(&lastHistoryID, historyID)
		return ingestNewestInbox(ctx, srv)
	}

	call := srv.Users.History.List("me").StartHistoryId(start).HistoryTypes("messageAdded").LabelId("INBOX")
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
		log.Printf("history.list from %d failed (%v); falling back to newest INBOX message", start, err)
		writeAuditLog(ctx, "fetch_history", fmt.Sprintf("history %d: %v (fell back)", start, err), false)
		atomic.StoreUint64(&lastHistoryID, historyID)
		return ingestNewestInbox(ctx, srv)
	}

	for _, msgID := range ids {
		err := ingestMessage(ctx, srv, msgID)
		if isPermanentIngestFailure(err) {
			// Retrying cannot help (deleted before the fetch, or a row the database refuses), and
			// failing the range would hold every newer message behind this one.
			writeAuditLog(ctx, "ingest_skipped", fmt.Sprintf("msg %s: %v", msgID, err), false)
			continue
		}
		if err != nil {
			// The baseline stays put, so the redelivery lists this range again and retries the
			// message; the ones already stored are skipped by messageStored.
			return fmt.Errorf("message %s: %w", msgID, err)
		}
	}
	advanceBaseline(historyID)
	return nil
}

// isPermanentIngestFailure is a failure that will recur on every retry: the message is gone from
// Gmail, or the database refused the row itself (a 4xx, not an outage).
func isPermanentIngestFailure(err error) bool {
	return err != nil && (isGone(err) || errors.Is(err, errRowRejected))
}

// advanceBaseline moves lastHistoryID forward only. Notifications are handled concurrently, and a
// slower, older one must not move the baseline back and make a newer range be listed twice.
func advanceBaseline(historyID uint64) {
	for {
		current := atomic.LoadUint64(&lastHistoryID)
		if historyID <= current || atomic.CompareAndSwapUint64(&lastHistoryID, current, historyID) {
			return
		}
	}
}

// ingestNewestInbox is the fallback for when history is unusable: the pre-#85 behaviour, kept
// because dropping the notification entirely would be worse than occasionally re-fetching.
func ingestNewestInbox(ctx context.Context, srv *gmail.Service) error {
	// INBOX only, matching the label the watch is registered against (setupWatch). Without it
	// this fetches the newest message anywhere in the mailbox — including a reply the system
	// just sent, which Gmail files in the same mailbox. That made AImail ingest its own outgoing
	// mail and generate replies to itself.
	list, err := srv.Users.Messages.List("me").LabelIds("INBOX").MaxResults(1).Do()
	if err != nil {
		writeAuditLog(ctx, "fetch_message", fmt.Sprintf("list error: %v", err), false)
		return fmt.Errorf("list messages: %w", err)
	}
	if len(list.Messages) == 0 {
		return nil
	}
	return ingestMessage(ctx, srv, list.Messages[0].Id)
}

// ingestMessage fetches one message by ID, masks its PII, and persists it plus an audit entry.
func ingestMessage(ctx context.Context, srv *gmail.Service, msgID string) error {
	// A failed lookup falls through to a normal ingest: dropping a message is worse than paying
	// for OCR twice, and the insert's on_conflict still keeps the row single.
	isStored, err := messageStored(ctx, msgID)
	if err != nil {
		log.Printf("could not check whether %s is stored, ingesting anyway: %v", msgID, err)
	}
	if isStored {
		return nil
	}

	msg, err := fetchMessage(ctx, srv, msgID)
	if err != nil {
		return err
	}
	if msg.Payload == nil {
		// Nothing to read or mask; a nil payload must not panic the Pub/Sub callback.
		writeAuditLog(ctx, "fetch_message", fmt.Sprintf("msg %s: no payload", msgID), false)
		return nil
	}
	identity := threadIdentity(msg)
	content, isComplete := maskMessage(ctx, srv, msg)
	if !isComplete {
		return quarantine(ctx, msgID, msg.Payload.Headers, identity)
	}

	stored := StoredMessage{
		GmailMessageID: msgID,
		FromAddr:       headerValue(msg.Payload.Headers, "From"), // kept as-is for reply threading; a policy call for the team to confirm
		ReplyTo:        headerValue(msg.Payload.Headers, "Reply-To"),
		ReceivedAt:     time.Now().UTC(),
		ThreadIdentity: identity,
		MaskedContent:  content,
	}
	isInserted, err := insertMessage(ctx, stored)
	if err != nil {
		log.Printf("could not store message %s: %v", msgID, err)
		writeAuditLog(ctx, "store_message", fmt.Sprintf("msg %s: %v", msgID, err), false)
		return fmt.Errorf("store message %s: %w", msgID, err)
	}
	if !isInserted {
		log.Printf("%s already stored; the insert was ignored", msgID)
		return nil
	}
	// Counts only: the sender, subject and body are never written to stdout.
	log.Printf("stored %s: %d bytes, %d emails / %d phones masked", msgID, len(content.BodyMasked),
		content.EmailsMasked, content.PhonesMasked)
	writeAuditLog(ctx, "store_message", fmt.Sprintf("msg %s stored, %d emails / %d phones masked",
		msgID, content.EmailsMasked, content.PhonesMasked), true)
	return nil
}

func fetchMessage(ctx context.Context, srv *gmail.Service, msgID string) (*gmail.Message, error) {
	msg, err := srv.Users.Messages.Get("me", msgID).Format("full").Context(ctx).Do()
	if err != nil {
		log.Printf("could not retrieve message %s: %v", msgID, err)
		writeAuditLog(ctx, "fetch_message", fmt.Sprintf("get error for %s: %v", msgID, err), false)
		return nil, fmt.Errorf("get message %s: %w", msgID, err)
	}
	return msg, nil
}

// maskMessage masks every content field. isComplete is false when NER was unavailable for any
// of them: the caller must then store nothing of the content (#109). Attachment text is masked on
// its own and dropped rather than degraded, so it never decides the outcome.
func maskMessage(ctx context.Context, srv *gmail.Service, msg *gmail.Message) (MaskedContent, bool) {
	maskedBody, bodyEmails, bodyPhones, degradedBody := maskText(ctx, getBody(msg.Payload))
	maskedSnippet, snipEmails, snipPhones, degradedSnip := maskText(ctx, msg.Snippet)
	maskedSubject, subEmails, subPhones, degradedSubj := maskText(ctx, headerValue(msg.Payload.Headers, "Subject"))
	if degradedBody || degradedSnip || degradedSubj {
		return MaskedContent{}, false
	}
	attachments, attachEmails, attachPhones := maskAttachmentText(ctx, msg.Id,
		ocrAttachments(ctx, srv, msg.Id, msg.Payload))
	return MaskedContent{
		Subject:       maskedSubject,
		BodyMasked:    maskedBody + attachments,
		SnippetMasked: maskedSnippet,
		EmailsMasked:  bodyEmails + snipEmails + subEmails + attachEmails,
		PhonesMasked:  bodyPhones + snipPhones + subPhones + attachPhones,
		MaskingStatus: maskingComplete,
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
	if plain := findPart(part, "text/plain"); plain != "" {
		return plain
	}
	if markup := findPart(part, "text/html"); markup != "" {
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

func findPart(part *gmail.MessagePart, mimeType string) string {
	if part.MimeType == mimeType {
		if body := decodePart(part); body != "" {
			return body
		}
	}
	for _, subPart := range part.Parts {
		if body := findPart(subPart, mimeType); body != "" {
			return body
		}
	}
	return ""
}

func decodePart(part *gmail.MessagePart) string {
	if part.Body == nil || part.Body.Data == "" {
		return ""
	}
	data, err := base64.URLEncoding.DecodeString(part.Body.Data)
	if err != nil {
		return ""
	}
	return string(data)
}

func main() {
	ctx := context.Background()

	// Load the shared root .env so SUPABASE_* are available without exporting them by hand.
	// Load does not override vars already set in the environment.
	if err := godotenv.Load("../.env"); err != nil {
		log.Printf("no ../.env loaded (%v); relying on the process environment", err)
	}
	supabaseURL = os.Getenv("SUPABASE_URL")
	supabaseKey = os.Getenv("SUPABASE_SERVICE_KEY")

	b, err := os.ReadFile("credentials.json")
	if err != nil {
		log.Fatalf("Unable to read client secret file: %v", err)
	}

	config, err := google.ConfigFromJSON(b,
		gmail.GmailReadonlyScope,
		gmail.GmailSendScope,
		"https://www.googleapis.com/auth/pubsub",
	)
	if err != nil {
		log.Fatalf("Unable to parse client secret file to config: %v", err)
	}

	tokFile := "token.json"
	tok, err := tokenFromFile(tokFile)
	if err != nil {
		tok = getTokenFromWeb(config)
		saveToken(tokFile, tok)
	}

	tokenSource := config.TokenSource(ctx, tok)
	client := config.Client(ctx, tok)

	srv, err := gmail.NewService(ctx, option.WithHTTPClient(client))
	if err != nil {
		log.Fatalf("Unable to retrieve Gmail client: %v", err)
	}

	if supabaseURL == "" || supabaseKey == "" {
		log.Println("WARNING: SUPABASE_URL / SUPABASE_SERVICE_KEY not set — storage and audit log writes will fail. Set these env vars before running.")
	}

	// 1. Establish Watch hook on Gmail API
	setupWatch(ctx, srv)

	// #83: keep the watch alive. Gmail expires it after about a week and nothing renewed it.
	go renewWatchPeriodically(ctx, srv)
	// #109: finish messages quarantined while Presidio was down.
	go remaskQuarantinedPeriodically(ctx, srv)

	// 2. Start live Pub/Sub listener loop
	listenToPubSub(ctx, tokenSource, srv)
}
