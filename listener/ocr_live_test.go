package main

// Live integration test for attachment reading. Exercises the real attachment-reader container
// and, when a key is configured, the real OCR call — skipping itself when either is unreachable,
// so `go test` stays green offline while the privacy claim stays verifiable locally
// (docker compose up -d from the repo root). Redaction itself is tested inside the container
// (make test-reader), against the real OCR and NER models.
//
// The claim under test is the ordering: nothing reads an image the local reader has not cleared.

import (
	"bytes"
	"context"
	"image"
	"image/color"
	"image/png"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/joho/godotenv"
)

func requireLiveReader(t *testing.T) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	if _, err := readLocally(ctx, testImagePNG(t), "image/png"); err != nil {
		t.Skipf("attachment reader unreachable (%v); run docker compose up -d", err)
	}
}

// testImagePNG is a blank page: no text for the local OCR to read, so nothing it could check.
func testImagePNG(t *testing.T) []byte {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, 600, 120))
	for x := 0; x < 600; x++ {
		for y := 0; y < 120; y++ {
			img.Set(x, y, color.White)
		}
	}
	var buf bytes.Buffer
	if err := png.Encode(&buf, img); err != nil {
		t.Fatalf("encode test image: %v", err)
	}
	return buf.Bytes()
}

func TestLiveReaderWithholdsAnImageItCouldNotRead(t *testing.T) {
	requireLiveReader(t)
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()

	result, err := readLocally(ctx, testImagePNG(t), "image/png")
	if err != nil {
		t.Fatalf("read failed: %v", err)
	}
	if len(result.Images) != 0 || result.SkippedPages != 1 {
		t.Fatalf("an image with no locally readable text must be withheld, got %+v", result)
	}
}

func TestLiveReaderFailureDoesNotFallThroughToOCR(t *testing.T) {
	// The ordering guarantee: if the reader cannot run, nothing reads the attachment. A fallback
	// that read it anyway would silently undo the reason this design exists.
	t.Setenv("ATTACHMENT_READER_URL", "http://127.0.0.1:1/read")
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	if _, err := readLocally(ctx, testImagePNG(t), "image/png"); err == nil {
		t.Fatal("an unreachable reader must return an error, never an unread attachment")
	}
}

func TestLiveOCRDoesNotNarrateABlankImage(t *testing.T) {
	_ = godotenv.Load("../.env")
	if getEnvOrDefault("OCR_MODEL", "") == "" || getEnvOrDefault("GOOGLE_API_KEY", "") == "" {
		t.Skip("OCR_MODEL / GOOGLE_API_KEY not configured")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()

	text, err := readRedactedImage(ctx, testImagePNG(t), "image/png")
	if err != nil {
		t.Fatalf("ocr failed: %v", err)
	}
	// A blank image should transcribe to nothing rather than to invented content — the failure
	// mode worth catching is a model that narrates an empty page.
	if len(strings.Fields(text)) > 12 {
		t.Fatalf("blank image produced %d words; the model is inventing text: %q", len(strings.Fields(text)), text)
	}
}

// The default for every owner: a scan's image stays here, and the text the local reader read from
// it is what the email keeps.
func TestLiveAScanReadLocallyKeepsItsText(t *testing.T) {
	requireLiveReader(t)
	raw, err := os.ReadFile(filepath.Join("testdata", "marks", "clear", "invoice.png"))
	if err != nil {
		t.Fatal(err)
	}
	result, err := readLocally(context.Background(), raw, "image/png")
	if err != nil {
		t.Fatal(err)
	}
	if len(result.Images) != 1 || !strings.Contains(result.Images[0].Text, "Amount due") {
		t.Fatalf("want one image with its local text, got %+v", result)
	}
	ocrCalls := recordOCRCalls(t)
	recordAuditRows(t)
	texts, sent := transcribeImages(context.Background(), messageRef{msgID: "m1"}, result.Images, reasonScansLocal)
	if sent != 0 || *ocrCalls != 0 || len(texts) != 1 || !strings.Contains(texts[0], "RM 1,250.00") {
		t.Fatalf("want the local text and nothing sent, got %d sent, %q", sent, texts)
	}
}
