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

// releasePatch completes a quarantined row. The verdict is written again because rows quarantined
// before it was stored hold the column defaults; from_addr and received_at stay as first written.
type releasePatch struct {
	SenderVerdict
	MaskedContent
	// Set at release as at ingest, so an email quarantined while Presidio was down still gets its floor.
	SlaPriority SLAPriority `json:"sla_priority,omitempty"`
}

type quarantinedRow struct {
	UserID          string `json:"user_id"` // null (token.json mailbox) decodes as ""
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

func quarantine(ctx context.Context, ownerID, msgID string, facts SenderFacts) error {
	row := QuarantinedMessage{UserID: ownerID, GmailMessageID: msgID, MaskingStatus: maskingPending, SenderFacts: facts}
	ref := messageRef{ownerID: ownerID, msgID: msgID}
	isInserted, err := insertMessage(ctx, row)
	if err != nil {
		ref.auditFailure(ctx, actionQuarantineMessage, stageStore, err)
		return fmt.Errorf("quarantine message %s: %w", msgID, err)
	}
	if !isInserted {
		return nil // already stored or already quarantined
	}
	log.Printf("quarantined %s: NER masking unavailable, content withheld until it is", msgID)
	ref.audit(ctx, actionQuarantineMessage, auditFields{fieldReason: reasonNERUnavailable}, true)
	return nil
}

// presidioHealthy asks the analyzer, the one container masking needs: replacement happens in this
// service since restorable masking, so the anonymizer is no longer on the path.
func presidioHealthy(ctx context.Context) bool {
	analyzer := getEnvOrDefault("PRESIDIO_ANALYZER_URL", "http://localhost:5001/analyze")
	return serviceHealthy(ctx, healthURL(analyzer, "/analyze"))
}

// healthURL turns a configured endpoint into its /health sibling, trailing slash or not.
func healthURL(endpoint, suffix string) string {
	return strings.TrimSuffix(strings.TrimRight(endpoint, "/"), suffix) + "/health"
}

func serviceHealthy(ctx context.Context, target string) bool {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, target, nil)
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
	query := fmt.Sprintf("select=user_id,gmail_message_id,masking_attempts&masking_status=eq.%s"+
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

// messageFilter selects one message of one mailbox; Gmail ids are only unique per mailbox.
func messageFilter(ownerID, msgID string) string {
	return ownerFilter(ownerID) + "&gmail_message_id=eq." + url.QueryEscape(msgID)
}

// abandon marks a message that can never be masked: its content is never stored.
func abandon(ctx context.Context, row quarantinedRow, reason string) {
	fields := map[string]interface{}{"masking_status": maskingAbandoned, "masking_attempts": row.MaskingAttempts + 1}
	if err := supabasePatch(ctx, "messages", messageFilter(row.UserID, row.GmailMessageID), fields); err != nil {
		log.Printf("could not abandon %s: %v", row.GmailMessageID, err)
		return
	}
	row.ref().audit(ctx, actionRemaskMessage,
		auditFields{fieldReason: reason, fieldAttempts: row.MaskingAttempts + 1, fieldMaskingStatus: maskingAbandoned}, false)
}

func (row quarantinedRow) ref() messageRef {
	return messageRef{ownerID: row.UserID, msgID: row.GmailMessageID}
}

// recordFailure counts one failed attempt, abandoning the row once it has used its attempts.
func recordFailure(ctx context.Context, row quarantinedRow, reason string) {
	if row.MaskingAttempts+1 >= maxRemaskAttempts {
		abandon(ctx, row, reason)
		return
	}
	fields := map[string]int{"masking_attempts": row.MaskingAttempts + 1}
	if err := supabasePatch(ctx, "messages", messageFilter(row.UserID, row.GmailMessageID), fields); err != nil {
		log.Printf("could not count attempt for %s: %v", row.GmailMessageID, err)
	}
}

func isGone(err error) bool {
	var apiErr *googleapi.Error
	return errors.As(err, &apiErr) && apiErr.Code == http.StatusNotFound
}

// isGmailTrouble is an outage rather than a problem with this message: a rate limit, a 5xx, or no
// answer at all. It must not use up the message's attempts, or one bad hour abandons the queue.
func isGmailTrouble(err error) bool {
	var apiErr *googleapi.Error
	if !errors.As(err, &apiErr) {
		return true
	}
	return apiErr.Code == http.StatusTooManyRequests || apiErr.Code >= http.StatusInternalServerError
}

// remaskQuarantined completes quarantined rows while NER is available. A row that fails is counted
// and skipped, so it cannot stall the rows behind it; if Presidio itself has gone down again the
// pass stops, since every remaining row would fail for the same reason.
func remaskQuarantined(ctx context.Context) {
	if !presidioHealthy(ctx) {
		return
	}
	rows, err := quarantinedRows(ctx)
	if err != nil {
		log.Printf("could not list quarantined messages: %v", err)
		return
	}
	for _, row := range rows {
		mb := mailboxByOwner(row.UserID)
		if mb == nil {
			continue // its mailbox is not connected right now; nothing is charged
		}
		if !remaskOne(ctx, mb.srv, row) {
			return
		}
	}
}

// remaskOne releases one row. It reports false when the pass should stop: Presidio or Gmail is
// down, so every remaining row would fail for the same reason and none of them should be charged.
func remaskOne(ctx context.Context, srv *gmail.Service, row quarantinedRow) bool {
	msg, err := fetchMessage(ctx, srv, row.ref())
	switch {
	case isGone(err):
		abandon(ctx, row, reasonGoneFromGmail)
		return true
	case err != nil && isGmailTrouble(err):
		return false
	case err != nil || msg.Payload == nil:
		recordFailure(ctx, row, reasonFetchFailed)
		return true
	}
	content, isComplete := maskMessage(ctx, srv, msg, row.UserID)
	if !isComplete {
		if !presidioHealthy(ctx) {
			return false
		}
		recordFailure(ctx, row, reasonMaskingIncomplete)
		return true
	}
	release := releasePatch{SenderVerdict: senderVerdict(msg.Payload.Headers), MaskedContent: content,
		SlaPriority: ClassifySLA(content.Subject, content.BodyMasked, time.Now().UTC())}
	if err := supabasePatch(ctx, "messages", messageFilter(row.UserID, row.GmailMessageID), release); err != nil {
		// Counted like any failure: a PATCH that always fails would otherwise re-read and re-OCR
		// the attachments every pass, forever.
		row.ref().auditFailure(ctx, actionRemaskMessage, stageStore, err)
		recordFailure(ctx, row, reasonStoreFailed)
		return true
	}
	row.ref().audit(ctx, actionRemaskMessage, auditFields{fieldReason: reasonReleased}, true)
	return true
}

func remaskQuarantinedPeriodically(ctx context.Context) {
	ticker := time.NewTicker(remaskInterval())
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			remaskQuarantined(ctx)
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
