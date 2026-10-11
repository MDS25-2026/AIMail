package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
)

// messageStored reports whether msgID already has a row. ingestMessage asks before fetching, so
// a Pub/Sub redelivery, the restart fallback to the newest message, or a retry never pays for
// attachment redaction and OCR a second time. The insert's on_conflict still guards the row itself.
func messageStored(ctx context.Context, ownerID, msgID string) (bool, error) {
	if supabaseURL == "" || supabaseKey == "" {
		return false, fmt.Errorf("SUPABASE_URL / SUPABASE_SERVICE_KEY not set")
	}
	query := "select=gmail_message_id&" + messageFilter(ownerID, msgID) + "&limit=1"
	req, err := http.NewRequestWithContext(ctx, http.MethodGet,
		fmt.Sprintf("%s/rest/v1/messages?%s", supabaseURL, query), nil)
	if err != nil {
		return false, fmt.Errorf("build request: %w", err)
	}
	req.Header.Set("apikey", supabaseKey)
	req.Header.Set("Authorization", "Bearer "+supabaseKey)

	resp, err := supabaseClient.Do(req)
	if err != nil {
		return false, fmt.Errorf("do request: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		return false, fmt.Errorf("supabase lookup failed: status %d", resp.StatusCode)
	}

	var rows []json.RawMessage
	if err := json.NewDecoder(resp.Body).Decode(&rows); err != nil {
		return false, fmt.Errorf("decode lookup: %w", err)
	}
	return len(rows) > 0, nil
}

// errRowRejected marks a 4xx from PostgREST: the row itself is refused, so retrying cannot help.
var errRowRejected = errors.New("supabase rejected the messages row")

// insertMessage inserts a messages row unless its mailbox already has one for its Gmail id (ids are
// per mailbox, so the key is the owner and the id together), and reports
// which happened. PostgREST returns the inserted rows; an ignored duplicate returns none, so an
// audit entry can say "stored" only when something was.
func insertMessage(ctx context.Context, row interface{}) (bool, error) {
	return insertIgnoringDuplicates(ctx, "messages", "user_id,gmail_message_id", "gmail_message_id", row)
}

// insertIgnoringDuplicates inserts a row, or nothing when one already holds its conflict key. It
// reports whether the row was new. A 4xx is the row itself refused, not an outage (errRowRejected).
func insertIgnoringDuplicates(ctx context.Context, table, onConflict, returned string, row interface{}) (bool, error) {
	if supabaseURL == "" || supabaseKey == "" {
		return false, fmt.Errorf("SUPABASE_URL / SUPABASE_SERVICE_KEY not set")
	}
	body, err := json.Marshal(row)
	if err != nil {
		return false, fmt.Errorf("marshal row: %w", err)
	}
	target := fmt.Sprintf("%s/rest/v1/%s?on_conflict=%s&select=%s", supabaseURL, table, onConflict, returned)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, target, bytes.NewReader(body))
	if err != nil {
		return false, fmt.Errorf("build request: %w", err)
	}
	req.Header.Set("apikey", supabaseKey)
	req.Header.Set("Authorization", "Bearer "+supabaseKey)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Prefer", "return=representation,resolution=ignore-duplicates")
	resp, err := supabaseClient.Do(req)
	if err != nil {
		return false, fmt.Errorf("do request: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 && resp.StatusCode < 500 {
		return false, fmt.Errorf("%w: status %d", errRowRejected, resp.StatusCode)
	}
	if resp.StatusCode >= 300 {
		return false, fmt.Errorf("supabase insert into %s failed: status %d", table, resp.StatusCode)
	}
	var inserted []json.RawMessage
	if err := json.NewDecoder(resp.Body).Decode(&inserted); err != nil {
		return false, fmt.Errorf("decode insert: %w", err)
	}
	return len(inserted) > 0, nil
}
