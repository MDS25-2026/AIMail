package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/url"
)

// messageStored reports whether msgID already has a row. ingestMessage asks before fetching, so
// a Pub/Sub redelivery, the restart fallback to the newest message, or a retry never pays for
// attachment redaction and OCR a second time. The insert's on_conflict still guards the row itself.
func messageStored(ctx context.Context, msgID string) (bool, error) {
	if supabaseURL == "" || supabaseKey == "" {
		return false, fmt.Errorf("SUPABASE_URL / SUPABASE_SERVICE_KEY not set")
	}
	query := "select=gmail_message_id&gmail_message_id=eq." + url.QueryEscape(msgID) + "&limit=1"
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

// insertMessage inserts a messages row unless one already exists for its Gmail id, and reports
// which happened. PostgREST returns the inserted rows; an ignored duplicate returns none, so an
// audit entry can say "stored" only when something was.
func insertMessage(ctx context.Context, row interface{}) (bool, error) {
	if supabaseURL == "" || supabaseKey == "" {
		return false, fmt.Errorf("SUPABASE_URL / SUPABASE_SERVICE_KEY not set")
	}
	body, err := json.Marshal(row)
	if err != nil {
		return false, fmt.Errorf("marshal row: %w", err)
	}
	target := fmt.Sprintf("%s/rest/v1/messages?on_conflict=gmail_message_id&select=gmail_message_id", supabaseURL)
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
		return false, fmt.Errorf("supabase insert into messages failed: status %d", resp.StatusCode)
	}
	var inserted []json.RawMessage
	if err := json.NewDecoder(resp.Body).Decode(&inserted); err != nil {
		return false, fmt.Errorf("decode insert: %w", err)
	}
	return len(inserted) > 0, nil
}
