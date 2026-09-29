package main

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"
)

func withSupabase(t *testing.T, handler http.HandlerFunc) *[]string {
	t.Helper()
	var queries []string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		queries = append(queries, r.URL.RawQuery)
		handler(w, r)
	}))
	t.Cleanup(server.Close)
	oldURL, oldKey := supabaseURL, supabaseKey
	supabaseURL, supabaseKey = server.URL, "test-key"
	t.Cleanup(func() { supabaseURL, supabaseKey = oldURL, oldKey })
	return &queries
}

func TestMessageStoredFindsAnExistingRow(t *testing.T) {
	withSupabase(t, func(w http.ResponseWriter, _ *http.Request) {
		w.Write([]byte(`[{"gmail_message_id":"abc"}]`))
	})
	stored, err := messageStored(context.Background(), "abc")
	if err != nil || !stored {
		t.Fatalf("want stored, got stored=%v err=%v", stored, err)
	}
}

func TestMessageStoredIsFalseForANewMessage(t *testing.T) {
	withSupabase(t, func(w http.ResponseWriter, _ *http.Request) {
		w.Write([]byte(`[]`))
	})
	stored, err := messageStored(context.Background(), "new")
	if err != nil || stored {
		t.Fatalf("want not stored, got stored=%v err=%v", stored, err)
	}
}

func TestMessageStoredEscapesTheID(t *testing.T) {
	queries := withSupabase(t, func(w http.ResponseWriter, _ *http.Request) {
		w.Write([]byte(`[]`))
	})
	if _, err := messageStored(context.Background(), "a&select=*"); err != nil {
		t.Fatal(err)
	}
	if got := (*queries)[0]; got != "select=gmail_message_id&gmail_message_id=eq.a%26select%3D%2A&limit=1" {
		t.Fatalf("id not escaped into the filter: %s", got)
	}
}

func TestMessageStoredReportsAnErrorRatherThanGuessing(t *testing.T) {
	withSupabase(t, func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	})
	if _, err := messageStored(context.Background(), "abc"); err == nil {
		t.Fatal("a failed lookup must be an error, not a silent 'not stored'")
	}
}
