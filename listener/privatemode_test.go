package main

import (
	"context"
	"encoding/base64"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func resetProviderCache(t *testing.T) {
	t.Helper()
	empty := func() {
		providerCache.Lock()
		providerCache.byOwner = map[string]cachedProvider{}
		providerCache.Unlock()
	}
	empty()
	t.Cleanup(empty)
}

// withPreferences answers user_preferences lookups with body (or status) and counts them.
func withPreferences(t *testing.T, status int, body string) *int {
	t.Helper()
	resetProviderCache(t)
	lookups := 0
	withSupabase(t, func(w http.ResponseWriter, r *http.Request) {
		if !strings.HasSuffix(r.URL.Path, "/user_preferences") {
			return
		}
		lookups++
		w.WriteHeader(status)
		w.Write([]byte(body))
	})
	return &lookups
}

func TestCloudOCRFollowsTheOwnersChoiceAndFailsClosed(t *testing.T) {
	cases := []struct {
		name   string
		owner  string
		status int
		body   string
		want   string
	}{
		{"checked scans", "user-a", http.StatusOK, `[{"draft_provider":"gemini","scan_reading":"checked"}]`, ""},
		{"local scans", "user-a", http.StatusOK, `[{"draft_provider":"gemini","scan_reading":"local"}]`, reasonScansLocal},
		{"never chose", "user-a", http.StatusOK, `[]`, reasonScansLocal},
		{"unknown scan value", "user-a", http.StatusOK, `[{"draft_provider":"gemini","scan_reading":"x"}]`, reasonScansLocal},
		{"Private mode", "user-a", http.StatusOK, `[{"draft_provider":"local"}]`, reasonPrivateMode},
		{"unknown value", "user-a", http.StatusOK, `[{"draft_provider":"other"}]`, reasonUnknownProvider},
		{"lookup fails", "user-a", http.StatusInternalServerError, `{}`, reasonLookupFailed},
		{"unreadable reply", "user-a", http.StatusOK, `not json`, reasonLookupFailed},
		{"no owner", "", http.StatusOK, `[{"draft_provider":"gemini"}]`, reasonOwnerUnknown},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			withPreferences(t, tc.status, tc.body)
			if got := cloudOCRRefusal(context.Background(), tc.owner); got != tc.want {
				t.Fatalf("want %q, got %q", tc.want, got)
			}
		})
	}
}

func TestAChoiceIsCachedButAFailureIsAskedAgain(t *testing.T) {
	lookups := withPreferences(t, http.StatusOK, `[{"draft_provider":"local"}]`)
	cloudOCRRefusal(context.Background(), "user-a")
	cloudOCRRefusal(context.Background(), "user-a")
	if *lookups != 1 {
		t.Fatalf("want one lookup within the TTL, got %d", *lookups)
	}
	failures := withPreferences(t, http.StatusInternalServerError, `{}`)
	cloudOCRRefusal(context.Background(), "user-b")
	cloudOCRRefusal(context.Background(), "user-b")
	if *failures != 2 {
		t.Fatalf("a failed lookup must not be cached, got %d lookups", *failures)
	}
}

// recordOCRCalls swaps the Gemini client for one that counts calls and answers with a transcription.
func recordOCRCalls(t *testing.T) *int {
	t.Helper()
	t.Setenv("OCR_MODEL", "test-model")
	t.Setenv("GOOGLE_API_KEY", "test-key")
	calls := 0
	original := ocrClient
	ocrClient = &http.Client{Transport: roundTripFunc(func(*http.Request) (*http.Response, error) {
		calls++
		reply := `{"candidates":[{"content":{"parts":[{"text":"Invoice 42"}]}}]}`
		return &http.Response{StatusCode: http.StatusOK, Body: io.NopCloser(strings.NewReader(reply)),
			Header: http.Header{}}, nil
	})}
	t.Cleanup(func() { ocrClient = original })
	return &calls
}

type roundTripFunc func(*http.Request) (*http.Response, error)

func (f roundTripFunc) RoundTrip(r *http.Request) (*http.Response, error) { return f(r) }

func testImages() []redactedImage {
	return []redactedImage{{MimeType: "image/png", Data: base64.StdEncoding.EncodeToString([]byte("png"))}}
}

func TestARefusedImageNeverReachesGeminiAndIsAudited(t *testing.T) {
	calls := recordOCRCalls(t)
	rows := recordAuditRows(t)
	texts, sent := transcribeImages(context.Background(), messageRef{ownerID: "user-a", msgID: "m1"},
		testImages(), reasonPrivateMode)
	if *calls != 0 || sent != 0 || len(texts) != 0 {
		t.Fatalf("a Private mode image was sent: %d calls, %d sent", *calls, sent)
	}
	if len(*rows) != 1 || (*rows)[0].Action != actionSkipCloudOCR || (*rows)[0].UserID != "user-a" {
		t.Fatalf("want one skip_cloud_ocr row, got %+v", *rows)
	}
}

// fakeReader stands in for the local attachment reader, returning one redacted image.
func fakeReader(t *testing.T) {
	t.Helper()
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Write([]byte(`{"text":"","images":[{"mime_type":"image/png","data":"cG5n","text":"Local invoice 7"}],"pages":1}`))
	}))
	t.Cleanup(server.Close)
	t.Setenv("ATTACHMENT_READER_URL", server.URL+"/read")
}

func TestAnOwnerWhoNeverChoseKeepsScansLocalAndGetsTheirText(t *testing.T) {
	calls := recordOCRCalls(t)
	fakeReader(t)
	withPreferences(t, http.StatusOK, `[]`)
	srv := fakeGmail(t, http.StatusOK, `{"data":"iVBORw0KGgoAAAAAAAAAAA=="}`)
	got := ocrAttachments(context.Background(), srv, messageRef{ownerID: "user-a", msgID: "m1"},
		imagePart("image/png", "att-1", 100))
	if *calls != 0 || !strings.Contains(got, "Local invoice 7") {
		t.Fatalf("want the local text and no Gemini call, got %d calls, text %q", *calls, got)
	}
}

func TestAPrivateModeOwnersAttachmentImagesStayLocal(t *testing.T) {
	calls := recordOCRCalls(t)
	fakeReader(t)
	withPreferences(t, http.StatusOK, `[{"draft_provider":"local"}]`)
	srv := fakeGmail(t, http.StatusOK, `{"data":"iVBORw0KGgoAAAAAAAAAAA=="}`) // a real PNG signature: the bytes are sniffed
	got := ocrAttachments(context.Background(), srv, messageRef{ownerID: "user-a", msgID: "m1"},
		imagePart("image/png", "att-1", 100))
	if *calls != 0 || !strings.Contains(got, "Local invoice 7") {
		t.Fatalf("a Private mode image reached Gemini or lost its text: %d calls, text %q", *calls, got)
	}
}

func TestACheckedScansOwnersClearImagesAreTranscribed(t *testing.T) {
	answerMarks(t, noMark)
	calls := recordOCRCalls(t)
	fakeReader(t)
	withPreferences(t, http.StatusOK, `[{"draft_provider":"gemini","scan_reading":"checked"}]`)
	srv := fakeGmail(t, http.StatusOK, `{"data":"iVBORw0KGgoAAAAAAAAAAA=="}`) // a real PNG signature: the bytes are sniffed
	got := ocrAttachments(context.Background(), srv, messageRef{ownerID: "user-a", msgID: "m1"},
		imagePart("image/png", "att-1", 100))
	if *calls != 1 || !strings.Contains(got, "Invoice 42") {
		t.Fatalf("want one transcription, got %d calls, text %q", *calls, got)
	}
}

func TestAnAllowedImageIsTranscribed(t *testing.T) {
	answerMarks(t, noMark)
	calls := recordOCRCalls(t)
	recordAuditRows(t)
	texts, sent := transcribeImages(context.Background(), messageRef{ownerID: "user-a", msgID: "m1"}, testImages(), "")
	if *calls != 1 || sent != 1 || len(texts) != 1 || texts[0] != "Invoice 42" {
		t.Fatalf("got %d calls, %d sent, %v", *calls, sent, texts)
	}
}
