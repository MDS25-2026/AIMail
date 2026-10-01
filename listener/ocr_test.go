package main

import (
	"strings"
	"testing"

	"google.golang.org/api/gmail/v1"
)

func imagePart(mime, attachmentID string, size int64) *gmail.MessagePart {
	return &gmail.MessagePart{
		MimeType: mime,
		Filename: "shot.png",
		Body:     &gmail.MessagePartBody{AttachmentId: attachmentID, Size: size},
	}
}

func TestImageAttachmentsFindsNestedImages(t *testing.T) {
	tree := &gmail.MessagePart{
		MimeType: "multipart/mixed",
		Parts: []*gmail.MessagePart{
			{MimeType: "text/plain", Body: &gmail.MessagePartBody{Data: "aGk="}},
			{MimeType: "multipart/related", Parts: []*gmail.MessagePart{
				imagePart("image/png", "att-1", 1000),
			}},
			imagePart("image/jpeg", "att-2", 2000),
		},
	}
	got := imageAttachments(tree, 5_000_000)
	if len(got) != 2 {
		t.Fatalf("want 2 image attachments, got %d", len(got))
	}
}

func TestImageAttachmentsIgnoresInlineImagesWithoutAttachmentID(t *testing.T) {
	// An image with no attachment id cannot be fetched, so treating it as one would just produce
	// a failed API call per message.
	tree := imagePart("image/png", "", 1000)
	if got := imageAttachments(tree, 5_000_000); len(got) != 0 {
		t.Fatalf("want 0, got %d", len(got))
	}
}

func TestImageAttachmentsRespectsSizeCap(t *testing.T) {
	tree := imagePart("image/png", "att-1", 9_000_000)
	if got := imageAttachments(tree, 5_000_000); len(got) != 0 {
		t.Fatalf("oversized attachment should be skipped, got %d", len(got))
	}
}

func TestImageAttachmentsIgnoresNonImages(t *testing.T) {
	tree := &gmail.MessagePart{MimeType: "multipart/mixed", Parts: []*gmail.MessagePart{
		{MimeType: "application/pdf", Body: &gmail.MessagePartBody{AttachmentId: "att-1", Size: 100}},
		{MimeType: "text/html", Body: &gmail.MessagePartBody{AttachmentId: "att-2", Size: 100}},
	}}
	if got := imageAttachments(tree, 5_000_000); len(got) != 0 {
		t.Fatalf("want 0 non-image attachments, got %d", len(got))
	}
}

func TestOCRMaxBytesRejectsNonsense(t *testing.T) {
	// A typo'd cap must not become "no cap" — that would let a 50 MB image stall ingestion.
	for _, value := range []string{"0", "-1", "big", ""} {
		t.Setenv("OCR_MAX_ATTACHMENT_BYTES", value)
		if got := ocrMaxBytes(); got != 5_000_000 {
			t.Fatalf("%q should fall back to 5000000, got %d", value, got)
		}
	}
}

func TestOCRMaxBytesReadsEnv(t *testing.T) {
	t.Setenv("OCR_MAX_ATTACHMENT_BYTES", "250000")
	if got := ocrMaxBytes(); got != 250_000 {
		t.Fatalf("want 250000, got %d", got)
	}
}

func TestOCRDisabledWithoutConfig(t *testing.T) {
	// No model or key configured must be a no-op, not an error: the text body still ingests.
	t.Setenv("OCR_MODEL", "")
	t.Setenv("GOOGLE_API_KEY", "")
	text, err := readRedactedImage(t.Context(), []byte("not really an image"), "image/png")
	if err != nil {
		t.Fatalf("unconfigured OCR should not error, got %v", err)
	}
	if text != "" {
		t.Fatalf("want empty text, got %q", text)
	}
}

func TestOCRPromptDoesNotInviteInterpretation(t *testing.T) {
	// This is a transcription step. A prompt asking the model to summarise or infer would put
	// its judgement between the image and what gets stored.
	lowered := strings.ToLower(ocrPrompt)
	for _, banned := range []string{"summar", "explain", "interpret", "describe what"} {
		if strings.Contains(lowered, banned) {
			t.Fatalf("ocr prompt should not ask the model to %q", banned)
		}
	}
	if !strings.Contains(lowered, "redacted") {
		t.Fatal("prompt must tell the model what the black boxes are, or it invents text for them")
	}
}

func TestOCRMarkerIsDistinguishable(t *testing.T) {
	// Stored text mixes body and attachment content; the boundary has to survive into the corpus
	// or nobody can tell later which part the model actually read.
	if !strings.Contains(ocrMarker, "attached image") {
		t.Fatalf("marker %q does not identify attachment text", ocrMarker)
	}
}
