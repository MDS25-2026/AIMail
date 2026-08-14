package main

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"regexp"
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
// Lane A floor is 80% masking accuracy. Regex-based email/phone masking is
// the v1 pass — good enough for the thin slice, not meant to be the final
// word. Lane B's classifier work can replace/augment this later if a
// smarter (e.g. NER-based) approach is needed to push accuracy up.

var (
	emailRegex = regexp.MustCompile(`[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}`)
	// Matches common phone formats: (123) 456-7890, 123-456-7890,
	// +60 12-345 6789, 0123456789, etc. Deliberately a bit loose —
	// prefers over-masking to under-masking given the audit-log context.
	phoneRegex = regexp.MustCompile(`(\+?\d{1,3}[\s.-]?)?(\(?\d{2,4}\)?[\s.-]?)\d{3,4}[\s.-]?\d{3,4}`)
)

// maskPII redacts emails and phone numbers from text, returning the masked
// text plus counts of how many of each were found (useful for the audit log
// and for tracking masking accuracy against the 80% floor).
func maskPII(text string) (masked string, emailsMasked, phonesMasked int) {
	masked = emailRegex.ReplaceAllStringFunc(text, func(s string) string {
		emailsMasked++
		return "[EMAIL_REDACTED]"
	})
	masked = phoneRegex.ReplaceAllStringFunc(masked, func(s string) string {
		phonesMasked++
		return "[PHONE_REDACTED]"
	})
	return masked, emailsMasked, phonesMasked
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

	// Mask PII before anything touches storage or logs.
	maskedBody, bodyEmails, bodyPhones := maskPII(body)
	maskedSnippet, snipEmails, snipPhones := maskPII(msg.Snippet)
	maskedSubject, subEmails, subPhones := maskPII(subject)
	totalEmails := bodyEmails + snipEmails + subEmails
	totalPhones := bodyPhones + snipPhones + subPhones

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

	writeAuditLog(ctx, "store_message", fmt.Sprintf("msg %s stored, %d emails / %d phones masked", msgID, totalEmails, totalPhones), true)
}

// getBody prefers the text/html part so the dashboard can render the email like a normal inbox;
// it falls back to text/plain, then to a single-part body.
func getBody(part *gmail.MessagePart) string {
	if html := findPart(part, "text/html"); html != "" {
		return html
	}
	if plain := findPart(part, "text/plain"); plain != "" {
		return plain
	}
	return decodePart(part)
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
