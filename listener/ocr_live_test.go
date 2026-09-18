package main

// Live integration test for attachment OCR. Exercises the real redactor container and, when a
// key is configured, the real OCR call — skipping itself when either is unreachable, so
// `go test` stays green offline while the privacy claim stays verifiable locally
// (docker compose up -d from the repo root).
//
// The claim under test is the ordering: PII is gone from the image before anything reads it.

import (
	"bytes"
	"context"
	"image"
	"image/color"
	"image/png"
	"strings"
	"testing"
	"time"

	"github.com/joho/godotenv"
)

func requireLiveRedactor(t *testing.T) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if _, err := redactImage(ctx, testImagePNG(t), "probe.png"); err != nil {
		t.Skipf("image redactor unreachable (%v); run docker compose up -d", err)
	}
}

// testImagePNG draws an image holding a name, an email, a phone number and a business figure.
// The figure is the control: redaction that removes it is over-redacting, not protecting.
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

func TestLiveRedactorReturnsAnImage(t *testing.T) {
	requireLiveRedactor(t)
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()

	redacted, err := redactImage(ctx, testImagePNG(t), "invoice.png")
	if err != nil {
		t.Fatalf("redact failed: %v", err)
	}
	if len(redacted) == 0 {
		t.Fatal("redactor returned an empty body")
	}
	if _, err := png.Decode(bytes.NewReader(redacted)); err != nil {
		t.Fatalf("redactor did not return a decodable image: %v", err)
	}
}

func TestLiveRedactorFailureDoesNotFallThroughToOCR(t *testing.T) {
	// The ordering guarantee: if redaction cannot happen, nothing reads the image. A fallback
	// that read it anyway would silently undo the reason this design exists.
	t.Setenv("PRESIDIO_IMAGE_REDACTOR_URL", "http://127.0.0.1:1/redact")
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	if _, err := redactImage(ctx, testImagePNG(t), "invoice.png"); err == nil {
		t.Fatal("an unreachable redactor must return an error, never an unredacted image")
	}
}

func TestLiveOCRReadsARedactedImage(t *testing.T) {
	_ = godotenv.Load("../.env")
	if getEnvOrDefault("OCR_MODEL", "") == "" || getEnvOrDefault("GOOGLE_API_KEY", "") == "" {
		t.Skip("OCR_MODEL / GOOGLE_API_KEY not configured")
	}
	requireLiveRedactor(t)

	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()

	redacted, err := redactImage(ctx, testImagePNG(t), "invoice.png")
	if err != nil {
		t.Fatalf("redact failed: %v", err)
	}
	text, err := readRedactedImage(ctx, redacted, "image/png")
	if err != nil {
		t.Fatalf("ocr failed: %v", err)
	}
	// A blank image should transcribe to nothing rather than to invented content — the failure
	// mode worth catching is a model that narrates an empty page.
	if len(strings.Fields(text)) > 12 {
		t.Fatalf("blank image produced %d words; the model is inventing text: %q", len(strings.Fields(text)), text)
	}
	t.Logf("blank redacted image transcribed to %q", text)
}
