package main

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"google.golang.org/api/googleapi"
)

func TestAQuarantinedRowCarriesNoContent(t *testing.T) {
	row := QuarantinedMessage{GmailMessageID: "m1", MaskingStatus: maskingPending,
		SenderFacts: SenderFacts{FromAddr: "a@b.c", ReceivedAt: time.Now()}}
	encoded, _ := json.Marshal(row)
	for _, column := range []string{"subject", "body_masked", "snippet_masked"} {
		if strings.Contains(string(encoded), column) {
			t.Fatalf("quarantined row must not carry %s: %s", column, encoded)
		}
	}
}

func TestAStoredRowIsMarkedComplete(t *testing.T) {
	encoded, _ := json.Marshal(StoredMessage{MaskedContent: MaskedContent{MaskingStatus: maskingComplete}})
	if !strings.Contains(string(encoded), `"masking_status":"complete"`) {
		t.Fatalf("stored row must say it is complete: %s", encoded)
	}
}

func TestQuarantinedRowsComeFewestAttemptsFirst(t *testing.T) {
	queries := withSupabase(t, func(w http.ResponseWriter, _ *http.Request) {
		w.Write([]byte(`[{"gmail_message_id":"a","masking_attempts":0},{"gmail_message_id":"b","masking_attempts":3}]`))
	})
	rows, err := quarantinedRows(context.Background())
	if err != nil || len(rows) != 2 || rows[1].MaskingAttempts != 3 {
		t.Fatalf("got %v, %v", rows, err)
	}
	q := (*queries)[0]
	if !strings.Contains(q, "masking_status=eq.pending") || !strings.Contains(q, "order=masking_attempts.asc,received_at.asc") {
		t.Fatalf("a failing row must not hold the head of the queue: %s", q)
	}
}

func TestAFailedAttemptIsCountedThenAbandoned(t *testing.T) {
	var bodies []string
	withSupabase(t, func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodPatch {
			raw, _ := io.ReadAll(r.Body)
			bodies = append(bodies, string(raw))
		}
	})
	recordFailure(context.Background(), quarantinedRow{GmailMessageID: "m", MaskingAttempts: 0}, "x")
	recordFailure(context.Background(), quarantinedRow{GmailMessageID: "m", MaskingAttempts: maxRemaskAttempts - 1}, "x")
	if len(bodies) != 2 || !strings.Contains(bodies[0], `"masking_attempts":1`) {
		t.Fatalf("first failure must only count: %v", bodies)
	}
	if !strings.Contains(bodies[1], `"masking_status":"abandoned"`) {
		t.Fatalf("the last attempt must abandon the row: %v", bodies)
	}
}

func TestAMessageGoneFromGmailIsRecognised(t *testing.T) {
	if !isGone(&googleapi.Error{Code: http.StatusNotFound}) || isGone(&googleapi.Error{Code: 500}) {
		t.Fatal("only a 404 means the message is gone")
	}
}

func TestReleasingAMessagePatchesOnlyItsContent(t *testing.T) {
	var method, body string
	withSupabase(t, func(w http.ResponseWriter, r *http.Request) {
		method = r.Method
		raw, _ := io.ReadAll(r.Body)
		body = string(raw)
	})
	err := supabasePatch(context.Background(), "messages", "gmail_message_id=eq.m1",
		MaskedContent{Subject: "Hi", MaskingStatus: maskingComplete})
	if err != nil || method != http.MethodPatch {
		t.Fatalf("want PATCH, got %s, %v", method, err)
	}
	if strings.Contains(body, "received_at") || !strings.Contains(body, `"masking_status":"complete"`) {
		t.Fatalf("patch must keep the original received_at and complete the row: %s", body)
	}
}

func TestPresidioHealthFollowsTheAnalyzerURL(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/health" {
			w.WriteHeader(http.StatusNotFound)
		}
	}))
	defer server.Close()
	t.Setenv("PRESIDIO_ANALYZER_URL", server.URL+"/analyze")
	t.Setenv("PRESIDIO_ANONYMIZER_URL", server.URL+"/anonymize")
	if !presidioHealthy(context.Background()) {
		t.Fatal("a healthy analyzer reported unhealthy")
	}
	t.Setenv("PRESIDIO_ANALYZER_URL", "http://127.0.0.1:1/analyze")
	if presidioHealthy(context.Background()) {
		t.Fatal("an unreachable analyzer reported healthy")
	}
}

func TestRemaskIntervalRejectsNonsense(t *testing.T) {
	for _, value := range []string{"", "soon", "-1m", "0s"} {
		t.Setenv("REMASK_INTERVAL", value)
		if got := remaskInterval(); got != 5*time.Minute {
			t.Fatalf("%q should fall back to 5m, got %v", value, got)
		}
	}
}
