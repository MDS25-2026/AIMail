package main

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"google.golang.org/api/gmail/v1"
	"google.golang.org/api/option"
)

// fakeGmail serves one message (or the given status) for any messages.get.
func fakeGmail(t *testing.T, status int, body string) *gmail.Service {
	t.Helper()
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(status)
		w.Write([]byte(body))
	}))
	t.Cleanup(server.Close)
	srv, err := gmail.NewService(context.Background(), option.WithEndpoint(server.URL+"/"),
		option.WithoutAuthentication(), option.WithHTTPClient(server.Client()))
	if err != nil {
		t.Fatal(err)
	}
	return srv
}

// fakePresidio answers health checks and finds no entities, so masking completes.
func fakePresidio(t *testing.T) {
	t.Helper()
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Write([]byte(`[]`))
	}))
	t.Cleanup(server.Close)
	t.Setenv("PRESIDIO_ANALYZER_URL", server.URL+"/analyze")
	t.Setenv("PRESIDIO_ANONYMIZER_URL", server.URL+"/anonymize")
}

func recordPatches(t *testing.T) *[]string {
	t.Helper()
	var patches []string
	withSupabase(t, func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodPatch {
			raw, _ := io.ReadAll(r.Body)
			patches = append(patches, string(raw))
		}
	})
	return &patches
}

func plainMessage(text string) string {
	encoded := base64.URLEncoding.EncodeToString([]byte(text))
	msg := map[string]interface{}{
		"id": "m1", "snippet": "Hello",
		"payload": map[string]interface{}{
			"mimeType": "text/plain",
			"headers":  []map[string]string{{"name": "Subject", "value": "Hello"}},
			"body":     map[string]string{"data": encoded},
		},
	}
	raw, _ := json.Marshal(msg)
	return string(raw)
}

func TestMaskingThatCannotRunNERIsIncompleteSoNothingIsStored(t *testing.T) {
	t.Setenv("PRESIDIO_ANALYZER_URL", "http://127.0.0.1:1/analyze")
	withSupabase(t, func(w http.ResponseWriter, _ *http.Request) {})
	msg := &gmail.Message{Id: "m1", Payload: &gmail.MessagePart{MimeType: "text/plain",
		Body: &gmail.MessagePartBody{Data: base64.URLEncoding.EncodeToString([]byte("Aisyah Rahman"))}}}
	if content, isComplete := maskMessage(context.Background(), nil, msg); isComplete || content.BodyMasked != "" {
		t.Fatal("without NER the message must be quarantined, with no content kept")
	}
}

func TestReleasingAQuarantinedMessageStoresItsMaskedContent(t *testing.T) {
	fakePresidio(t)
	patches := recordPatches(t)
	srv := fakeGmail(t, http.StatusOK, plainMessage("Call me on 012-345 6789 please"))
	if !remaskOne(context.Background(), srv, quarantinedRow{GmailMessageID: "m1"}) {
		t.Fatal("a healthy pass must continue")
	}
	if len(*patches) != 1 || !strings.Contains((*patches)[0], `"masking_status":"complete"`) {
		t.Fatalf("want one completing patch, got %v", *patches)
	}
	if strings.Contains((*patches)[0], "345 6789") {
		t.Fatal("the regex floor must mask the phone number before storing")
	}
}

func TestAMessageDeletedFromGmailIsAbandoned(t *testing.T) {
	fakePresidio(t)
	patches := recordPatches(t)
	srv := fakeGmail(t, http.StatusNotFound, `{"error":{"code":404,"message":"gone"}}`)
	remaskOne(context.Background(), srv, quarantinedRow{GmailMessageID: "m1"})
	if len(*patches) != 1 || !strings.Contains((*patches)[0], `"masking_status":"abandoned"`) {
		t.Fatalf("want the row abandoned, got %v", *patches)
	}
}

func TestAGmailOutageStopsThePassWithoutChargingAttempts(t *testing.T) {
	fakePresidio(t)
	patches := recordPatches(t)
	srv := fakeGmail(t, http.StatusServiceUnavailable, `{"error":{"code":503,"message":"down"}}`)
	if remaskOne(context.Background(), srv, quarantinedRow{GmailMessageID: "m1"}) {
		t.Fatal("an outage must stop the pass")
	}
	if len(*patches) != 0 {
		t.Fatalf("an outage must not count against the message: %v", *patches)
	}
}

func TestHealthRequiresBothPresidioContainers(t *testing.T) {
	healthy := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {}))
	defer healthy.Close()
	t.Setenv("PRESIDIO_ANALYZER_URL", healthy.URL+"/analyze/")
	t.Setenv("PRESIDIO_ANONYMIZER_URL", "http://127.0.0.1:1/anonymize")
	if presidioHealthy(context.Background()) {
		t.Fatal("an unreachable anonymizer must make Presidio unhealthy")
	}
	t.Setenv("PRESIDIO_ANONYMIZER_URL", healthy.URL+"/anonymize")
	if !presidioHealthy(context.Background()) {
		t.Fatal("both up (with a trailing slash on one URL) is healthy")
	}
}
