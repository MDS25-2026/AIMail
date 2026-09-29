package main

// Quarantine for messages whose masking could not complete (#109).
//
// Masking used to degrade to the regex floor when Presidio was down, and a stored message kept a
// real name and town that way. Now nothing of the content is stored until NER can run: the row
// holds only what is needed to show the message exists and to finish it, and a background loop
// re-fetches and masks it once Presidio answers its health check.

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"net/url"
	"strings"
	"time"

	"google.golang.org/api/gmail/v1"
	"google.golang.org/api/googleapi"
)

const (
	maskingComplete  = "complete"
	maskingPending   = "pending"
	maskingAbandoned = "abandoned"
	// A bounded batch per pass: re-reading attachments is slow, and the next pass picks up the rest.
	remaskBatchSize = 20
	// About an hour of failures at the default 5 m interval while Presidio itself is healthy: a
	// message that still cannot be masked by then is abandoned, never stored degraded.
	maxRemaskAttempts = 12
)

type quarantinedRow struct {
	GmailMessageID  string `json:"gmail_message_id"`
	MaskingAttempts int    `json:"masking_attempts"`
}

func remaskInterval() time.Duration {
	minutes, err := time.ParseDuration(getEnvOrDefault("REMASK_INTERVAL", "5m"))
	if err != nil || minutes <= 0 {
		return 5 * time.Minute
	}
	return minutes
}

func quarantine(ctx context.Context, msgID string, headers []*gmail.MessagePartHeader, identity ThreadIdentity) error {
	row := QuarantinedMessage{
		GmailMessageID: msgID,
		FromAddr:       headerValue(headers, "From"),
		ReplyTo:        headerValue(headers, "Reply-To"),
		ReceivedAt:     time.Now().UTC(),
		MaskingStatus:  maskingPending,
		ThreadIdentity: identity,
	}
	if err := supabaseInsert(ctx, "messages", row, "gmail_message_id"); err != nil {
		writeAuditLog(ctx, "quarantine_message", fmt.Sprintf("msg %s: %v", msgID, err), false)
		return fmt.Errorf("quarantine message %s: %w", msgID, err)
	}
	log.Printf("quarantined %s: NER masking unavailable, content withheld until it is", msgID)
	writeAuditLog(ctx, "quarantine_message",
		fmt.Sprintf("msg %s: NER unavailable, content withheld", msgID), true)
	return nil
}

// presidioHealthy asks the analyzer's /health, derived from its configured /analyze URL.
func presidioHealthy(ctx context.Context) bool {
	analyze := getEnvOrDefault("PRESIDIO_ANALYZER_URL", "http://localhost:5001/analyze")
	req, err := http.NewRequestWithContext(ctx, http.MethodGet,
		strings.TrimSuffix(analyze, "/analyze")+"/health", nil)
	if err != nil {
		return false
	}
	resp, err := presidioClient.Do(req)
	if err != nil {
		return false
	}
	resp.Body.Close()
	return resp.StatusCode < 300
}

// quarantinedRows lists pending rows, fewest attempts first, so a message that keeps failing
// sinks behind newer ones instead of holding the head of the queue.
func quarantinedRows(ctx context.Context) ([]quarantinedRow, error) {
	query := fmt.Sprintf("select=gmail_message_id,masking_attempts&masking_status=eq.%s"+
		"&order=masking_attempts.asc,received_at.asc&limit=%d", maskingPending, remaskBatchSize)
	body, err := supabaseGet(ctx, "messages", query)
	if err != nil {
		return nil, err
	}
	var rows []quarantinedRow
	if err := json.Unmarshal(body, &rows); err != nil {
		return nil, fmt.Errorf("decode quarantined rows: %w", err)
	}
	return rows, nil
}

func messageFilter(msgID string) string {
	return "gmail_message_id=eq." + url.QueryEscape(msgID)
}

// abandon marks a message that can never be masked: its content is never stored.
func abandon(ctx context.Context, row quarantinedRow, reason string) {
	fields := map[string]interface{}{"masking_status": maskingAbandoned, "masking_attempts": row.MaskingAttempts + 1}
	if err := supabasePatch(ctx, "messages", messageFilter(row.GmailMessageID), fields); err != nil {
		log.Printf("could not abandon %s: %v", row.GmailMessageID, err)
		return
	}
	writeAuditLog(ctx, "remask_message", fmt.Sprintf("msg %s abandoned: %s", row.GmailMessageID, reason), false)
}

// recordFailure counts one failed attempt, abandoning the row once it has used its attempts.
func recordFailure(ctx context.Context, row quarantinedRow, reason string) {
	if row.MaskingAttempts+1 >= maxRemaskAttempts {
		abandon(ctx, row, reason)
		return
	}
	fields := map[string]int{"masking_attempts": row.MaskingAttempts + 1}
	if err := supabasePatch(ctx, "messages", messageFilter(row.GmailMessageID), fields); err != nil {
		log.Printf("could not count attempt for %s: %v", row.GmailMessageID, err)
	}
}

func isGone(err error) bool {
	var apiErr *googleapi.Error
	return errors.As(err, &apiErr) && apiErr.Code == http.StatusNotFound
}

// remaskQuarantined completes quarantined rows while NER is available. A row that fails is counted
// and skipped, so it cannot stall the rows behind it; if Presidio itself has gone down again the
// pass stops, since every remaining row would fail for the same reason.
func remaskQuarantined(ctx context.Context, srv *gmail.Service) {
	if !presidioHealthy(ctx) {
		return
	}
	rows, err := quarantinedRows(ctx)
	if err != nil {
		log.Printf("could not list quarantined messages: %v", err)
		return
	}
	for _, row := range rows {
		if !remaskOne(ctx, srv, row) {
			return
		}
	}
}

// remaskOne releases one row. It reports false only when Presidio has gone down mid-pass.
func remaskOne(ctx context.Context, srv *gmail.Service, row quarantinedRow) bool {
	msg, err := fetchMessage(ctx, srv, row.GmailMessageID)
	if isGone(err) {
		abandon(ctx, row, "no longer in Gmail")
		return true
	}
	if err != nil {
		recordFailure(ctx, row, "fetch failed")
		return true
	}
	content, isComplete := maskMessage(ctx, srv, msg)
	if !isComplete {
		if !presidioHealthy(ctx) {
			return false
		}
		recordFailure(ctx, row, "masking did not complete")
		return true
	}
	if err := supabasePatch(ctx, "messages", messageFilter(row.GmailMessageID), content); err != nil {
		writeAuditLog(ctx, "remask_message", fmt.Sprintf("msg %s: %v", row.GmailMessageID, err), false)
		return true
	}
	writeAuditLog(ctx, "remask_message", fmt.Sprintf("msg %s released from quarantine", row.GmailMessageID), true)
	return true
}

func remaskQuarantinedPeriodically(ctx context.Context, srv *gmail.Service) {
	ticker := time.NewTicker(remaskInterval())
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			remaskQuarantined(ctx, srv)
		}
	}
}

func supabaseGet(ctx context.Context, table, query string) ([]byte, error) {
	return supabaseRequest(ctx, http.MethodGet, fmt.Sprintf("%s/rest/v1/%s?%s", supabaseURL, table, query), nil)
}

// supabasePatch updates the rows matching filter (a PostgREST filter, already escaped).
func supabasePatch(ctx context.Context, table, filter string, fields interface{}) error {
	body, err := json.Marshal(fields)
	if err != nil {
		return fmt.Errorf("marshal patch: %w", err)
	}
	_, err = supabaseRequest(ctx, http.MethodPatch,
		fmt.Sprintf("%s/rest/v1/%s?%s", supabaseURL, table, filter), body)
	return err
}

func supabaseRequest(ctx context.Context, method, target string, body []byte) ([]byte, error) {
	if supabaseURL == "" || supabaseKey == "" {
		return nil, fmt.Errorf("SUPABASE_URL / SUPABASE_SERVICE_KEY not set")
	}
	req, err := http.NewRequestWithContext(ctx, method, target, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("build request: %w", err)
	}
	req.Header.Set("apikey", supabaseKey)
	req.Header.Set("Authorization", "Bearer "+supabaseKey)
	req.Header.Set("Content-Type", "application/json")
	resp, err := supabaseClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("do request: %w", err)
	}
	defer resp.Body.Close()
	var out bytes.Buffer
	if _, err := out.ReadFrom(resp.Body); err != nil {
		return nil, fmt.Errorf("read response: %w", err)
	}
	if resp.StatusCode >= 300 {
		return nil, fmt.Errorf("supabase %s %s failed: status %d", method, table(target), resp.StatusCode)
	}
	return out.Bytes(), nil
}

// table names the resource in an error without echoing the query, which may carry an id filter.
func table(target string) string {
	path := strings.SplitN(target, "?", 2)[0]
	return path[strings.LastIndex(path, "/")+1:]
}
