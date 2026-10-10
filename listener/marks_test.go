package main

import (
	"context"
	"errors"
	"io"
	"net/http"
	"strings"
	"testing"
)

// answerMarks swaps the local model for one that answers each image with the next reply in turn,
// and counts the calls.
func answerMarks(t *testing.T, replies ...string) *int {
	t.Helper()
	t.Setenv("LOCAL_VISION_MODEL", "test-vision")
	calls := 0
	original := markClient
	markClient = &http.Client{Transport: roundTripFunc(func(*http.Request) (*http.Response, error) {
		reply := replies[min(calls, len(replies)-1)]
		calls++
		return &http.Response{StatusCode: http.StatusOK, Body: io.NopCloser(strings.NewReader(reply)),
			Header: http.Header{}}, nil
	})}
	t.Cleanup(func() { markClient = original })
	return &calls
}

const (
	noMark   = `{"response":"{\"signature\": false, \"face\": false, \"stamp\": false}"}`
	markSeen = `{"response":"{\"signature\": false, \"face\": false, \"stamp\": true}"}`
)

func threeImages() []redactedImage {
	img := testImages()[0]
	img.Text = "Local text"
	return []redactedImage{img, img, img}
}

func withheldRows(rows []AuditLogEntry, reason string) int {
	total := 0
	for _, row := range rows {
		if row.Action == actionSkipCloudOCR && strings.Contains(row.Detail, reason) {
			total++
		}
	}
	return total
}

func TestAnImageWithASignatureFaceOrStampNeverReachesGemini(t *testing.T) {
	answerMarks(t, noMark, markSeen, noMark)
	ocrCalls := recordOCRCalls(t)
	rows := recordAuditRows(t)
	texts, sent := transcribeImages(context.Background(), messageRef{ownerID: "user-a", msgID: "m1"}, threeImages(), "")
	if sent != 2 || *ocrCalls != 2 {
		t.Fatalf("want the two clear images sent, got %d sent, %d Gemini calls", sent, *ocrCalls)
	}
	if len(texts) != 3 || texts[1] != "Local text" {
		t.Fatalf("the withheld image must keep its local text, got %q", texts)
	}
	if withheldRows(*rows, reasonMarkFound) != 1 {
		t.Fatalf("want one audit row for the withheld image, got %+v", *rows)
	}
}

func TestAFailedTranscriptionFallsBackToTheLocalText(t *testing.T) {
	answerMarks(t, noMark)
	t.Setenv("OCR_MODEL", "")
	recordAuditRows(t)
	texts, _ := transcribeImages(context.Background(), messageRef{msgID: "m1"}, threeImages()[:1], "")
	if len(texts) != 1 || texts[0] != "Local text" {
		t.Fatalf("got %q", texts)
	}
}

func TestWithNoLocalVisionModelEveryImageStaysLocal(t *testing.T) {
	t.Setenv("LOCAL_VISION_MODEL", "")
	ocrCalls := recordOCRCalls(t)
	rows := recordAuditRows(t)
	texts, sent := transcribeImages(context.Background(), messageRef{ownerID: "user-a", msgID: "m1"}, threeImages(), "")
	if sent != 0 || *ocrCalls != 0 || withheldRows(*rows, reasonNoMarkCheck) != 1 || len(texts) != 3 {
		t.Fatalf("an image left with no check configured: %d sent, %d calls, rows %+v", sent, *ocrCalls, *rows)
	}
}

func TestAnUnclearAnswerCountsAsAMark(t *testing.T) {
	for _, reply := range []string{
		`{"response":"maybe"}`, `{"response":"{}"}`,
		`{"response":"{\"signature\": false, \"face\": false}"}`,
		`{"response":"{\"signature\": \"no\", \"face\": false, \"stamp\": false}"}`,
	} {
		answerMarks(t, reply)
		recordOCRCalls(t)
		recordAuditRows(t)
		if _, sent := transcribeImages(context.Background(), messageRef{msgID: "m1"}, testImages(), ""); sent != 0 {
			t.Fatalf("reply %s let the image through", reply)
		}
	}
}

func TestAnUnreachableModelWithholdsTheRestWithoutAskingAgain(t *testing.T) {
	t.Setenv("LOCAL_VISION_MODEL", "test-vision")
	calls := 0
	original := markClient
	markClient = &http.Client{Transport: roundTripFunc(func(*http.Request) (*http.Response, error) {
		calls++
		return nil, errors.New("connection refused")
	})}
	t.Cleanup(func() { markClient = original })
	ocrCalls := recordOCRCalls(t)
	recordAuditRows(t)
	_, sent := transcribeImages(context.Background(), messageRef{msgID: "m1"}, threeImages(), "")
	if sent != 0 || *ocrCalls != 0 || calls != 1 {
		t.Fatalf("want nothing sent after one failed call, got %d sent, %d model calls", sent, calls)
	}
}

func TestAModelErrorStatusWithholds(t *testing.T) {
	t.Setenv("LOCAL_VISION_MODEL", "test-vision")
	original := markClient
	markClient = &http.Client{Transport: roundTripFunc(func(*http.Request) (*http.Response, error) {
		return &http.Response{StatusCode: http.StatusNotFound, Body: io.NopCloser(strings.NewReader(`{}`)),
			Header: http.Header{}}, nil
	})}
	t.Cleanup(func() { markClient = original })
	recordOCRCalls(t)
	recordAuditRows(t)
	if _, sent := transcribeImages(context.Background(), messageRef{msgID: "m1"}, testImages(), ""); sent != 0 {
		t.Fatal("an image was sent after the local model answered 404")
	}
}
