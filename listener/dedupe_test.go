package main

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"google.golang.org/api/gmail/v1"
	"google.golang.org/api/option"
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
	stored, err := messageStored(context.Background(), "", "abc")
	if err != nil || !stored {
		t.Fatalf("want stored, got stored=%v err=%v", stored, err)
	}
}

func TestMessageStoredIsFalseForANewMessage(t *testing.T) {
	withSupabase(t, func(w http.ResponseWriter, _ *http.Request) {
		w.Write([]byte(`[]`))
	})
	stored, err := messageStored(context.Background(), "", "new")
	if err != nil || stored {
		t.Fatalf("want not stored, got stored=%v err=%v", stored, err)
	}
}

func TestMessageStoredEscapesTheID(t *testing.T) {
	queries := withSupabase(t, func(w http.ResponseWriter, _ *http.Request) {
		w.Write([]byte(`[]`))
	})
	if _, err := messageStored(context.Background(), "", "a&select=*"); err != nil {
		t.Fatal(err)
	}
	if got := (*queries)[0]; got != "select=gmail_message_id&user_id=is.null&gmail_message_id=eq.a%26select%3D%2A&limit=1" {
		t.Fatalf("id not escaped into the filter: %s", got)
	}
}

func TestMessageStoredReportsAnErrorRatherThanGuessing(t *testing.T) {
	withSupabase(t, func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	})
	if _, err := messageStored(context.Background(), "", "abc"); err == nil {
		t.Fatal("a failed lookup must be an error, not a silent 'not stored'")
	}
}

func TestAnIgnoredDuplicateIsNotReportedAsStored(t *testing.T) {
	withSupabase(t, func(w http.ResponseWriter, r *http.Request) {
		if !strings.Contains(r.Header.Get("Prefer"), "return=representation") {
			t.Error("the insert must ask for the rows it wrote")
		}
		w.Write([]byte(`[]`))
	})
	isInserted, err := insertMessage(context.Background(), map[string]string{"gmail_message_id": "m1"})
	if err != nil || isInserted {
		t.Fatalf("an empty reply means nothing was inserted: %v %v", isInserted, err)
	}
}

func TestOversizeAttachmentsAreCounted(t *testing.T) {
	tree := &gmail.MessagePart{MimeType: "multipart/mixed", Parts: []*gmail.MessagePart{
		{MimeType: "application/pdf", Body: &gmail.MessagePartBody{AttachmentId: "a", Size: 9_000_000}},
		{MimeType: "image/png", Body: &gmail.MessagePartBody{AttachmentId: "b", Size: 100}},
	}}
	if got := oversizeAttachments(tree, 5_000_000); got != 1 {
		t.Fatalf("want 1 oversize attachment, got %d", got)
	}
}

func TestTheHistoryBaselineOnlyMovesForward(t *testing.T) {
	mb := &mailbox{lastHistoryID: 100}
	advanceBaseline(mb, 90)
	if mb.lastHistoryID != 100 {
		t.Fatal("an older notification moved the baseline back")
	}
	advanceBaseline(mb, 120)
	if mb.lastHistoryID != 120 {
		t.Fatal("a newer notification did not advance the baseline")
	}
}

func TestAFailureThatWillRecurIsSkippedNotRetried(t *testing.T) {
	withSupabase(t, func(w http.ResponseWriter, _ *http.Request) { w.WriteHeader(http.StatusBadRequest) })
	_, err := insertMessage(context.Background(), map[string]string{"gmail_message_id": "m1"})
	if !isPermanentIngestFailure(err) {
		t.Fatalf("a 4xx insert must count as permanent: %v", err)
	}
	withSupabase(t, func(w http.ResponseWriter, _ *http.Request) { w.WriteHeader(http.StatusServiceUnavailable) })
	_, err = insertMessage(context.Background(), map[string]string{"gmail_message_id": "m1"})
	if isPermanentIngestFailure(err) {
		t.Fatal("an outage must stay retryable")
	}
}

func TestTheCatchUpIngestsRecentMailOldestFirstAndSkipsWhatIsStored(t *testing.T) {
	var looked []string
	withSupabase(t, func(w http.ResponseWriter, r *http.Request) {
		looked = append(looked, r.URL.Query().Get("gmail_message_id"))
		w.Write([]byte(`[{"gmail_message_id":"stored"}]`)) // every one already stored: nothing is fetched
	})
	mb := &mailbox{srv: fakeGmail(t, http.StatusOK, `{"messages":[{"id":"m3"},{"id":"m2"},{"id":"m1"}]}`)}
	if err := ingestHistory(context.Background(), mb, 500); err != nil {
		t.Fatal(err)
	}
	if strings.Join(looked, ",") != "eq.m1,eq.m2,eq.m3" || mb.lastHistoryID != 500 {
		t.Fatalf("looked up %v, baseline %d", looked, mb.lastHistoryID)
	}
}

func TestAFailedCatchUpLeavesTheBaselineForTheRetry(t *testing.T) {
	withSupabase(t, func(w http.ResponseWriter, _ *http.Request) { w.Write([]byte(`[]`)) }) // nothing stored yet
	// The list answers; fetching the message hits an outage, as during a blip mid catch-up.
	gmailServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		if strings.HasSuffix(r.URL.Path, "/messages") {
			w.Write([]byte(`{"messages":[{"id":"m1"}]}`))
			return
		}
		w.WriteHeader(http.StatusServiceUnavailable)
		w.Write([]byte(`{"error":{"code":503,"message":"down"}}`))
	}))
	t.Cleanup(gmailServer.Close)
	srv, err := gmail.NewService(context.Background(), option.WithEndpoint(gmailServer.URL+"/"),
		option.WithoutAuthentication(), option.WithHTTPClient(gmailServer.Client()))
	if err != nil {
		t.Fatal(err)
	}
	mb := &mailbox{srv: srv}
	if err := ingestHistory(context.Background(), mb, 500); err == nil {
		t.Fatal("a catch-up that could not store its mail must fail the notification")
	}
	if mb.lastHistoryID != 0 {
		t.Fatalf("the baseline moved to %d past mail that was never stored", mb.lastHistoryID)
	}
}

func TestAGmailOutageIsRetriedFromTheSameBaselineNotCaughtUp(t *testing.T) {
	var lookups int
	withSupabase(t, func(w http.ResponseWriter, _ *http.Request) { lookups++ })
	mb := &mailbox{srv: fakeGmail(t, http.StatusServiceUnavailable, `{}`), lastHistoryID: 100}
	if err := ingestHistory(context.Background(), mb, 500); err == nil {
		t.Fatal("a 503 from history.list must fail the notification")
	}
	if mb.lastHistoryID != 100 || lookups != 0 {
		t.Fatalf("baseline %d after %d lookups: an outage fell back to a catch-up", mb.lastHistoryID, lookups)
	}
}
