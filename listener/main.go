package main

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"html"
	"io"
	"log"
	"net/http"
	"os"
	"regexp"
	"strconv"
	"strings"
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

// --- PII masking -----------------------------------------------------------
//
// Format-clear PII (email, phone, Malaysian IC) is redacted here by deterministic, ordered
// regex — most-specific first, so an IC is masked before the phone pattern can see its
// digits. Context-dependent PII (names, locations, orgs, account numbers) is left to
// Presidio's NER below. Splitting by PII *nature* rather than by tool is what removes the
// "different-length numbers, wrong type" mis-tagging: no two patterns fight over one span.

const (
	emailToken = "[EMAIL_REDACTED]"
	phoneToken = "[PHONE_REDACTED]"
	icToken    = "[IC_REDACTED]"
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
	masked = emailRegex.ReplaceAllStringFunc(text, func(string) string {
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
	masked = phoneRegex.ReplaceAllStringFunc(masked, func(string) string {
		phonesMasked++
		return phoneToken
	})
	return masked, emailsMasked, phonesMasked
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
		Context:  []string{"account", "acc", "bank", "maybank", "cimb", "rhb", "public bank", "transfer", "reference", "ref", "passport", "policy", "member"},
	},
}

// maskText applies the regex PII floor first (always, offline-proof), then layers Presidio
// NER on the floored text. On any Presidio error it degrades to the regex result — raw text
// is never returned. emails/phones counts come from the regex pass so they stay honest in
// both modes; degraded reports whether Presidio ran, for the audit log.
func maskText(ctx context.Context, text string) (masked string, emailsMasked, phonesMasked int, degraded bool) {
	masked, emailsMasked, phonesMasked = maskPII(text)
	presidioMasked, err := maskWithPresidio(ctx, masked)
	if err != nil {
		log.Printf("presidio degraded, regex-only for this field: %v", err)
		return masked, emailsMasked, phonesMasked, true
	}
	return presidioMasked, emailsMasked, phonesMasked, false
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
		Text:             text,
		Language:         "en",
		ScoreThreshold:   0.6,
		Entities:         []string{"PERSON", "LOCATION", "ORGANIZATION", "ACCOUNT_NUMBER"},
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

// StoredMessage is what we persist for each processed email, post-masking.
type StoredMessage struct {
	GmailMessageID string    `json:"gmail_message_id"`
	FromAddr       string    `json:"from_addr"`
	Subject        string    `json:"subject"`
	BodyMasked     string    `json:"body_masked"`
	SnippetMasked  string    `json:"snippet_masked"`
	EmailsMasked   int       `json:"emails_masked"`
	PhonesMasked   int       `json:"phones_masked"`
	ReceivedAt     time.Time `json:"received_at"`
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

	resp, err := http.DefaultClient.Do(req)
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
		msg.Ack()

		var payload struct {
			EmailAddress string `json:"emailAddress"`
			HistoryID    uint64 `json:"historyId"`
		}
		if err := json.Unmarshal(msg.Data, &payload); err != nil {
			log.Printf("Error unmarshalling Pub/Sub data: %v", err)
			return
		}

		fmt.Printf("\nNew email event received for: %s (History ID: %d)\n", payload.EmailAddress, payload.HistoryID)
		fetchLatestMessage(ctx, srv)
	})

	if err != nil {
		log.Fatalf("Error receiving Pub/Sub messages: %v", err)
	}
}

// Fetches the most recent message, masks PII, and persists it + an audit
// log entry to Supabase.
func fetchLatestMessage(ctx context.Context, srv *gmail.Service) {
	list, err := srv.Users.Messages.List("me").MaxResults(1).Do()
	if err != nil || len(list.Messages) == 0 {
		log.Printf("Could not fetch messages: %v", err)
		writeAuditLog(ctx, "fetch_message", fmt.Sprintf("list error: %v", err), false)
		return
	}

	msgID := list.Messages[0].Id
	msg, err := srv.Users.Messages.Get("me", msgID).Format("full").Do()
	if err != nil {
		log.Printf("Could not retrieve message details: %v", err)
		writeAuditLog(ctx, "fetch_message", fmt.Sprintf("get error for %s: %v", msgID, err), false)
		return
	}

	var subject, from string
	for _, h := range msg.Payload.Headers {
		if h.Name == "Subject" {
			subject = h.Value
		}
		if h.Name == "From" {
			from = h.Value
		}
	}

	body := getBody(msg.Payload)

	// Mask PII before anything touches storage or logs: regex floor first, then Presidio NER.
	maskedBody, bodyEmails, bodyPhones, degradedBody := maskText(ctx, body)
	maskedSnippet, snipEmails, snipPhones, degradedSnip := maskText(ctx, msg.Snippet)
	maskedSubject, subEmails, subPhones, degradedSubj := maskText(ctx, subject)
	totalEmails := bodyEmails + snipEmails + subEmails
	totalPhones := bodyPhones + snipPhones + subPhones
	presidioDegraded := degradedBody || degradedSnip || degradedSubj

	fmt.Println("-------------------------------------------")
	fmt.Printf("FROM: %s\n", from)
	fmt.Printf("SUBJECT (masked): %s\n", maskedSubject)
	fmt.Printf("BODY SNIPPET (masked): %s\n", maskedSnippet)
	fmt.Printf("FULL BODY LENGTH: %d bytes | masked %d emails, %d phones\n", len(body), totalEmails, totalPhones)
	fmt.Println("-------------------------------------------")

	stored := StoredMessage{
		GmailMessageID: msgID,
		FromAddr:       from, // sender address kept as-is for reply threading; masking here is a policy call for the team to confirm
		Subject:        maskedSubject,
		BodyMasked:     maskedBody,
		SnippetMasked:  maskedSnippet,
		EmailsMasked:   totalEmails,
		PhonesMasked:   totalPhones,
		ReceivedAt:     time.Now().UTC(),
	}

	if err := supabaseInsert(ctx, "messages", stored, "gmail_message_id"); err != nil {
		log.Printf("Could not store message: %v", err)
		writeAuditLog(ctx, "store_message", fmt.Sprintf("msg %s: %v", msgID, err), false)
		return
	}

	detail := fmt.Sprintf("msg %s stored, %d emails / %d phones masked", msgID, totalEmails, totalPhones)
	if presidioDegraded {
		detail += " (presidio degraded: regex-only)"
	}
	writeAuditLog(ctx, "store_message", detail, true)
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
	blankLineRegex = regexp.MustCompile(`\n{3,}`)
)

// htmlToText reduces email HTML to prose. Deliberately regex-based rather than a full parser:
// the goal is feeding clean sentences to the masker, not faithful rendering, and a parser would
// add a dependency for no gain here. Block-closing tags become newlines so sentences do not run
// together, which would confuse NER as much as the tags did.
func htmlToText(markup string) string {
	text := htmlDropRegex.ReplaceAllString(markup, " ")
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

	// 2. Start live Pub/Sub listener loop
	listenToPubSub(ctx, tokenSource, srv)
}
