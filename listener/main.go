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
	"strings"
	"time"

	"cloud.google.com/go/pubsub"
	"golang.org/x/oauth2"
	"golang.org/x/oauth2/google"
	"google.golang.org/api/gmail/v1"
	"google.golang.org/api/option"
)

// GCP Pub/Sub Config for project aimail-505405
var (
	projectID      = getEnvOrDefault("GCP_PROJECT_ID", "aimail-505405")
	topicName      = getEnvOrDefault("GCP_PUBSUB_TOPIC", "projects/aimail-505405/topics/aimail-notifications")
	subscriptionID = getEnvOrDefault("GCP_PUBSUB_SUBSCRIPTION", "aimail-notifications-sub")
)

// Supabase config
var (
	supabaseURL = os.Getenv("SUPABASE_URL")
	supabaseKey = os.Getenv("SUPABASE_SERVICE_KEY")
)

func getEnvOrDefault(key, fallback string) string {
	if val := os.Getenv(key); val != "" {
		return val
	}
	return fallback
}

// --- Presidio PII Masking Structs & Functions -------------------------------

type PresidioPattern struct {
	Name  string  `json:"name"`
	Regex string  `json:"regex"`
	Score float64 `json:"score"`
}

type PresidioAdHocRecognizer struct {
	Name              string            `json:"name"`
	SupportedLanguage string            `json:"supported_language"`
	SupportedEntity   string            `json:"supported_entity"`
	Patterns          []PresidioPattern `json:"patterns"`
	Context           []string          `json:"context,omitempty"`
}

type PresidioAnalyzeRequest struct {
	Text             string                    `json:"text"`
	Language         string                    `json:"language"`
	ScoreThreshold   float64                   `json:"score_threshold"`
	Entities         []string                  `json:"entities,omitempty"`
	AdHocRecognizers []PresidioAdHocRecognizer `json:"ad_hoc_recognizers,omitempty"`
}

type PresidioRecognizerResult struct {
	EntityType string  `json:"entity_type"`
	Start      int     `json:"start"`
	End        int     `json:"end"`
	Score      float64 `json:"score"`
}

type PresidioAnonymizeRequest struct {
	Text           string                     `json:"text"`
	AnalyzeResults []PresidioRecognizerResult `json:"analyzer_results"`
	Anonymizers    map[string]interface{}     `json:"anonymizers,omitempty"`
}

type PresidioAnonymizeResponse struct {
	Text string `json:"text"`
}

// maskWithPresidio calls local Presidio containers and replaces PII with [Redacted]
func maskWithPresidio(ctx context.Context, text string) (string, int, error) {
	if strings.TrimSpace(text) == "" {
		return "", 0, nil
	}

	analyzerURL := getEnvOrDefault("PRESIDIO_ANALYZER_URL", "http://localhost:5001/analyze")
	anonymizerURL := getEnvOrDefault("PRESIDIO_ANONYMIZER_URL", "http://localhost:5002/anonymize")

	customRecognizers := []PresidioAdHocRecognizer{
		{
			Name:              "MY_IC_RECOGNIZER",
			SupportedLanguage: "en",
			SupportedEntity:   "MY_IC",
			Patterns: []PresidioPattern{
				{
					Name:  "my_ic_pattern",
					Regex: `\b\d{6}-\d{2}-\d{4,7}\b|\b\d{12}\b`,
					Score: 1.0,
				},
			},
		},
		{
			Name:              "MY_PHONE_RECOGNIZER",
			SupportedLanguage: "en",
			SupportedEntity:   "PHONE_NUMBER",
			Patterns: []PresidioPattern{
				{
					Name:  "my_phone_pattern",
					Regex: `\b(\+?60|0)[1-9]\d{7,8}\b|\b(\+?60\s?|0)\d{1,2}[\s.-]?\d{3,4}[\s.-]?\d{3,4}\b`,
					Score: 0.95,
				},
			},
		},
		{
			Name:              "FLEXIBLE_ACCOUNT_RECOGNIZER",
			SupportedLanguage: "en",
			SupportedEntity:   "ACCOUNT_NUMBER",
			Patterns: []PresidioPattern{
				{
					Name:  "arbitrary_digit_pattern",
					Regex: `\b\d{6,16}\b`,
					Score: 0.4,
				},
			},
			Context: []string{
				"account", "acc", "bank", "maybank", "cimb", "rhb", "public bank",
				"transfer", "reference", "ref", "passport", "policy", "member",
			},
		},
	}

	analyzePayload, err := json.Marshal(PresidioAnalyzeRequest{
		Text:           text,
		Language:       "en",
		ScoreThreshold: 0.6,
		Entities: []string{
			"PERSON",
			"PHONE_NUMBER",
			"EMAIL_ADDRESS",
			"LOCATION",
			"ORGANIZATION",
			"MY_IC",
			"ACCOUNT_NUMBER",
		},
		AdHocRecognizers: customRecognizers,
	})
	if err != nil {
		return text, 0, err
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, analyzerURL, bytes.NewReader(analyzePayload))
	if err != nil {
		return text, 0, err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return text, 0, fmt.Errorf("presidio analyzer error: %w", err)
	}
	defer resp.Body.Close()

	var analyzeResults []PresidioRecognizerResult
	if err := json.NewDecoder(resp.Body).Decode(&analyzeResults); err != nil {
		return text, 0, err
	}

	if len(analyzeResults) == 0 {
		return text, 0, nil
	}

	anonymizersConfig := map[string]interface{}{
		"DEFAULT": map[string]interface{}{
			"type":      "replace",
			"new_value": "[Redacted]",
		},
	}

	anonymizePayload, err := json.Marshal(PresidioAnonymizeRequest{
		Text:           text,
		AnalyzeResults: analyzeResults,
		Anonymizers:    anonymizersConfig,
	})
	if err != nil {
		return text, len(analyzeResults), err
	}

	req2, err := http.NewRequestWithContext(ctx, http.MethodPost, anonymizerURL, bytes.NewReader(anonymizePayload))
	if err != nil {
		return text, len(analyzeResults), err
	}
	req2.Header.Set("Content-Type", "application/json")

	resp2, err := http.DefaultClient.Do(req2)
	if err != nil {
		return text, len(analyzeResults), fmt.Errorf("presidio anonymizer error: %w", err)
	}
	defer resp2.Body.Close()

	var anonymizeResp PresidioAnonymizeResponse
	if err := json.NewDecoder(resp2.Body).Decode(&anonymizeResp); err != nil {
		return text, len(analyzeResults), err
	}

	return anonymizeResp.Text, len(analyzeResults), nil
}

// --- Supabase storage + audit log -------------------------------------------

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

type AuditLogEntry struct {
	Action    string    `json:"action"`
	Detail    string    `json:"detail"`
	Success   bool      `json:"success"`
	CreatedAt time.Time `json:"created_at"`
}

func supabaseInsert(ctx context.Context, table string, row interface{}) error {
	if supabaseURL == "" || supabaseKey == "" {
		return fmt.Errorf("SUPABASE_URL / SUPABASE_SERVICE_KEY not set")
	}

	body, err := json.Marshal(row)
	if err != nil {
		return fmt.Errorf("marshal row: %w", err)
	}

	url := fmt.Sprintf("%s/rest/v1/%s", supabaseURL, table)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("build request: %w", err)
	}
	req.Header.Set("apikey", supabaseKey)
	req.Header.Set("Authorization", "Bearer "+supabaseKey)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Prefer", "return=minimal")

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

func writeAuditLog(ctx context.Context, action, detail string, success bool) {
	entry := AuditLogEntry{
		Action:    action,
		Detail:    detail,
		Success:   success,
		CreatedAt: time.Now().UTC(),
	}
	if err := supabaseInsert(ctx, "audit_log", entry); err != nil {
		log.Printf("audit log write failed: %v", err)
	}
}

func loadSecret(filePath, envVar string) ([]byte, error) {
	data, err := os.ReadFile(filePath)
	if err == nil {
		return data, nil
	}
	if envVal := os.Getenv(envVar); envVal != "" {
		return []byte(envVal), nil
	}
	return nil, fmt.Errorf("neither file %s nor env var %s found", filePath, envVar)
}

func tokenFromFile(file string) (*oauth2.Token, error) {
	tokData, err := loadSecret(file, "GMAIL_TOKEN_JSON")
	if err != nil {
		return nil, err
	}
	tok := &oauth2.Token{}
	err = json.Unmarshal(tokData, tok)
	return tok, err
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

func saveToken(path string, token *oauth2.Token) {
	fmt.Printf("Saving credential file to: %s\n", path)
	f, err := os.OpenFile(path, os.O_RDWR|os.O_CREATE|os.O_TRUNC, 0600)
	if err != nil {
		log.Fatalf("Unable to cache oauth token: %v", err)
	}
	defer f.Close()
	json.NewEncoder(f).Encode(token)
}

func setupWatch(ctx context.Context, srv *gmail.Service) {
	req := &gmail.WatchRequest{
		TopicName: topicName,
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

func listenToPubSub(ctx context.Context, ts oauth2.TokenSource, srv *gmail.Service) {
	client, err := pubsub.NewClient(ctx, projectID, option.WithTokenSource(ts))
	if err != nil {
		log.Fatalf("Failed to create Pub/Sub client: %v", err)
	}
	defer client.Close()

	sub := client.Subscription(subscriptionID)
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

	maskedBody, bodyPIICount, err := maskWithPresidio(ctx, body)
	if err != nil {
		log.Printf("Presidio body masking error: %v", err)
	}

	maskedSnippet, snipPIICount, _ := maskWithPresidio(ctx, msg.Snippet)
	maskedSubject, subPIICount, _ := maskWithPresidio(ctx, subject)

	totalPIIMasked := bodyPIICount + snipPIICount + subPIICount

	fmt.Println("-------------------------------------------")
	fmt.Printf("FROM: %s\n", from)
	fmt.Printf("SUBJECT (masked): %s\n", maskedSubject)
	fmt.Printf("BODY SNIPPET (masked): %s\n", maskedSnippet)
	fmt.Printf("FULL BODY LENGTH: %d bytes | Presidio Redact Count: %d\n", len(body), totalPIIMasked)
	fmt.Println("-------------------------------------------")

	stored := StoredMessage{
		GmailMessageID: msgID,
		FromAddr:       from,
		Subject:        maskedSubject,
		BodyMasked:     maskedBody,
		SnippetMasked:  maskedSnippet,
		EmailsMasked:   totalPIIMasked,
		PhonesMasked:   0,
		ReceivedAt:     time.Now().UTC(),
	}

	if err := supabaseInsert(ctx, "messages", stored); err != nil {
		log.Printf("Could not store message: %v", err)
		writeAuditLog(ctx, "store_message", fmt.Sprintf("msg %s: %v", msgID, err), false)
		return
	}

	writeAuditLog(ctx, "store_message", fmt.Sprintf("msg %s stored, %d PII entities masked by Presidio", msgID, totalPIIMasked), true)
}

func getBody(part *gmail.MessagePart) string {
	if part.Body != nil && part.Body.Data != "" {
		data, err := base64.URLEncoding.DecodeString(part.Body.Data)
		if err == nil {
			return string(data)
		}
	}
	for _, subPart := range part.Parts {
		body := getBody(subPart)
		if body != "" {
			return body
		}
	}
	return ""
}

func main() {
	ctx := context.Background()

	b, err := loadSecret("credentials.json", "GMAIL_CREDENTIALS_JSON")
	if err != nil {
		log.Fatalf("Unable to read client secret: %v", err)
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
		log.Println("WARNING: SUPABASE_URL / SUPABASE_SERVICE_KEY not set — storage and audit log writes will fail.")
	}

	setupWatch(ctx, srv)
	listenToPubSub(ctx, tokenSource, srv)
}