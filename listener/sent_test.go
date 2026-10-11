package main

import (
	"context"
	"io"
	"net/http"
	"strings"
	"testing"
)

// recordInserts answers every Supabase call and records the tables rows were posted to.
func recordInserts(t *testing.T) *[]string {
	t.Helper()
	var tables []string
	withSupabase(t, func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodPost {
			raw, _ := io.ReadAll(r.Body)
			tables = append(tables, strings.TrimPrefix(r.URL.Path, "/rest/v1/")+" "+string(raw))
			w.Write([]byte(`[{"gmail_id":"s1"}]`))
			return
		}
		w.Write([]byte(`[]`))
	})
	return &tables
}

func sentMessage(labels, extraHeader string) string {
	return `{"id":"s1","threadId":"t1","internalDate":"1791302400000","labelIds":[` + labels + `],
		"payload":{"mimeType":"text/plain","headers":[{"name":"Subject","value":"Re: Invoice"}` + extraHeader + `],
		"body":{"data":"Q291bGQgeW91IHNlbmQgdGhlIFBPPw"}}}`
}

func TestASentReplyIsStoredForTheWaitingListAndNeverAsReceivedMail(t *testing.T) {
	fakePresidio(t)
	inserts := recordInserts(t)
	srv := fakeGmail(t, http.StatusOK, sentMessage(`"SENT"`, ""))
	if err := ingestSentMessage(context.Background(), &mailbox{srv: srv, ownerID: "user-a"}, "s1"); err != nil {
		t.Fatal(err)
	}
	if len(*inserts) != 1 || !strings.HasPrefix((*inserts)[0], "sent_message ") {
		t.Fatalf("want one sent_message row and no messages row, got %v", *inserts)
	}
	if !strings.Contains((*inserts)[0], `"body_masked":"Could you send the PO?"`) ||
		!strings.Contains((*inserts)[0], `"thread_id":"t1"`) {
		t.Fatalf("row is missing its content: %s", (*inserts)[0])
	}
}

func TestMailToYourselfAndAutomaticRepliesAreNotKeptAsSentReplies(t *testing.T) {
	fakePresidio(t)
	for _, msg := range []string{
		sentMessage(`"SENT","INBOX"`, ""),
		sentMessage(`"SENT"`, `,{"name":"Auto-Submitted","value":"auto-replied"}`),
	} {
		inserts := recordInserts(t)
		srv := fakeGmail(t, http.StatusOK, msg)
		if err := ingestSentMessage(context.Background(), &mailbox{srv: srv}, "s1"); err != nil {
			t.Fatal(err)
		}
		if len(*inserts) != 0 {
			t.Fatalf("stored what it should skip: %v", *inserts)
		}
	}
}

func TestASentReplyThatCannotBeMaskedIsSkippedNotStoredDegraded(t *testing.T) {
	t.Setenv("PRESIDIO_ANALYZER_URL", "http://127.0.0.1:1/analyze")
	t.Setenv("PRESIDIO_ANONYMIZER_URL", "http://127.0.0.1:1/anonymize")
	inserts := recordInserts(t)
	srv := fakeGmail(t, http.StatusOK, sentMessage(`"SENT"`, ""))
	mb := &mailbox{srv: srv, ownerID: "user-a"}
	if err := ingestSentMessage(context.Background(), mb, "s1"); err != errSentNotMasked {
		t.Fatalf("want errSentNotMasked, got %v", err)
	}
	ingestSent(context.Background(), mb, []string{"s1"}) // recorded and skipped, never a panic or a stop
	for _, insert := range *inserts {
		if strings.HasPrefix(insert, "sent_message ") {
			t.Fatalf("stored a degraded sent reply: %s", insert)
		}
	}
}

func TestOnlyAnAutoSubmittedValueOtherThanNoIsAnAutomaticReply(t *testing.T) {
	for value, want := range map[string]bool{"": false, "no": false, "No": false, "auto-replied": true, "auto-generated": true} {
		if got := isAutoReply(value); got != want {
			t.Errorf("%q: got %v, want %v", value, got, want)
		}
	}
}
