package main

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"io"
	"net/http"
	"strings"
	"testing"
)

// spoofedAutomatedMessage fails Google's SPF check and comes from a no-reply sender.
func spoofedAutomatedMessage() string {
	msg := map[string]interface{}{
		"id": "m1", "threadId": "t1", "snippet": "Your account",
		"payload": map[string]interface{}{
			"mimeType": "text/plain",
			"headers": []map[string]string{
				{"name": "From", "value": "no-reply@bank.example"},
				{"name": "Subject", "value": "Your account"},
				{"name": "Authentication-Results", "value": googleSPFFail},
			},
			"body": map[string]string{"data": base64.URLEncoding.EncodeToString([]byte("Verify now"))},
		},
	}
	raw, _ := json.Marshal(msg)
	return string(raw)
}

// recordMessageWrites captures every body written to the messages table, answering an insert as stored.
func recordMessageWrites(t *testing.T) *[]string {
	t.Helper()
	var bodies []string
	withSupabase(t, func(w http.ResponseWriter, r *http.Request) {
		if !strings.HasSuffix(r.URL.Path, "/messages") {
			return
		}
		if r.Method == http.MethodGet {
			w.Write([]byte(`[]`))
			return
		}
		raw, _ := io.ReadAll(r.Body)
		bodies = append(bodies, string(raw))
		w.Write([]byte(`[{"gmail_message_id":"m1"}]`))
	})
	return &bodies
}

func requireVerdict(t *testing.T, body string) {
	t.Helper()
	if !strings.Contains(body, `"auth_status":"spoof_detected"`) || !strings.Contains(body, `"is_automated":true`) {
		t.Fatalf("the sender verdict was not written: %s", body)
	}
}

func TestAQuarantinedSpoofKeepsItsVerdict(t *testing.T) {
	t.Setenv("PRESIDIO_ANALYZER_URL", "http://127.0.0.1:1/analyze")
	writes := recordMessageWrites(t)
	mb := &mailbox{srv: fakeGmail(t, http.StatusOK, spoofedAutomatedMessage())}
	if err := ingestMessage(context.Background(), mb, "m1"); err != nil {
		t.Fatal(err)
	}
	if len(*writes) != 1 || !strings.Contains((*writes)[0], `"masking_status":"pending"`) {
		t.Fatalf("want one quarantined insert, got %v", *writes)
	}
	requireVerdict(t, (*writes)[0])
}

func TestReleasingAQuarantinedSpoofKeepsItsVerdict(t *testing.T) {
	fakePresidio(t)
	writes := recordMessageWrites(t)
	srv := fakeGmail(t, http.StatusOK, spoofedAutomatedMessage())
	if !remaskOne(context.Background(), srv, quarantinedRow{GmailMessageID: "m1"}) {
		t.Fatal("a healthy pass must continue")
	}
	if len(*writes) != 1 || !strings.Contains((*writes)[0], `"masking_status":"complete"`) {
		t.Fatalf("want one completing patch, got %v", *writes)
	}
	requireVerdict(t, (*writes)[0])
}

func TestAStoredSpoofKeepsItsVerdict(t *testing.T) {
	fakePresidio(t)
	writes := recordMessageWrites(t)
	mb := &mailbox{srv: fakeGmail(t, http.StatusOK, spoofedAutomatedMessage())}
	if err := ingestMessage(context.Background(), mb, "m1"); err != nil {
		t.Fatal(err)
	}
	if len(*writes) != 1 || !strings.Contains((*writes)[0], `"masking_status":"complete"`) {
		t.Fatalf("want one stored insert, got %v", *writes)
	}
	requireVerdict(t, (*writes)[0])
}

func TestTheSendersOffsetIsReadFromTheirDateHeader(t *testing.T) {
	cases := []struct {
		date string
		want *int
	}{
		{"Tue, 7 Oct 2026 23:40:00 +0800", intPointer(480)},
		{"Tue, 7 Oct 2026 10:40:00 -0530", intPointer(-330)},
		{"7 Oct 2026 15:40:00 GMT", intPointer(0)},
		{"", nil},
		{"next Tuesday", nil},
	}
	for _, tc := range cases {
		got := utcOffsetMinutes(tc.date)
		if (got == nil) != (tc.want == nil) || (got != nil && *got != *tc.want) {
			t.Errorf("%q: got %v, want %v", tc.date, got, tc.want)
		}
	}
}

func intPointer(n int) *int { return &n }
