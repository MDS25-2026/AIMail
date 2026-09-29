package main

import (
	"context"
	"encoding/json"
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
