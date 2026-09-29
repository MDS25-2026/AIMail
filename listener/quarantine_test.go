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
)

func TestAQuarantinedRowCarriesNoContent(t *testing.T) {
	row := QuarantinedMessage{GmailMessageID: "m1", FromAddr: "a@b.c", ReceivedAt: time.Now(),
		MaskingStatus: maskingPending}
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

func TestQuarantinedIDsAsksForPendingRowsOldestFirst(t *testing.T) {
	queries := withSupabase(t, func(w http.ResponseWriter, _ *http.Request) {
		w.Write([]byte(`[{"gmail_message_id":"a"},{"gmail_message_id":"b"}]`))
	})
	ids, err := quarantinedIDs(context.Background())
	if err != nil || len(ids) != 2 || ids[0] != "a" {
		t.Fatalf("got %v, %v", ids, err)
	}
	if q := (*queries)[0]; !strings.Contains(q, "masking_status=eq.pending") || !strings.Contains(q, "order=received_at.asc") {
		t.Fatalf("unexpected query %s", q)
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
