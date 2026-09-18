package main

// Attachment OCR (#82).
//
// The ordering here is the whole point. An attachment image is redacted by Presidio on this
// machine *first*, and only the redacted image is ever read by the model. That keeps the
// mask-before-transit guarantee true for attachments, which no cloud-OCR-first design can:
// reading an image is what finds the PII in it, so anything that reads it remotely sees the PII
// before masking can happen.
//
// Presidio's image redactor returns an image, not text — there is no text endpoint — so a reader
// is still needed. Gemini reads the redacted image. By then there is nothing sensitive left in it.

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"strconv"
	"strings"
	"time"

	"google.golang.org/api/gmail/v1"
)

const (
	geminiEndpoint = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent"

	// Deliberately flat and literal. An instruction to summarise or interpret would put model
	// judgement between the image and the stored text, and this is a transcription step.
	ocrPrompt = "Transcribe all text visible in this image, exactly as it appears. " +
		"Black rectangles are redacted content: write [REDACTED] where one appears. " +
		"Return only the transcription, with no commentary. " +
		"If the image contains no text, return nothing."

	ocrMarker = "\n\n--- text from attached image ---\n"
)

// Redacting and reading are both slow enough to need generous deadlines, and both are bounded so
// a stuck call cannot hold the Pub/Sub receive callback open (the same failure as #86).
var (
	redactorClient = &http.Client{Timeout: 60 * time.Second}
	ocrClient      = &http.Client{Timeout: 90 * time.Second}
)

func ocrMaxBytes() int64 {
	size, err := strconv.ParseInt(getEnvOrDefault("OCR_MAX_ATTACHMENT_BYTES", "5000000"), 10, 64)
	if err != nil || size <= 0 {
		return 5_000_000
	}
	return size
}

// imageAttachments walks the MIME tree for image parts carrying an attachment id.
func imageAttachments(part *gmail.MessagePart, max int64) []*gmail.MessagePart {
	var found []*gmail.MessagePart
	if strings.HasPrefix(part.MimeType, "image/") &&
		part.Body != nil && part.Body.AttachmentId != "" && part.Body.Size <= max {
		found = append(found, part)
	}
	for _, sub := range part.Parts {
		found = append(found, imageAttachments(sub, max)...)
	}
	return found
}

// redactImage blacks out PII inside the image. An error here must fail the attachment rather than
// fall through to OCR: sending an unredacted image onward is the one outcome this design exists to
// prevent, so degrading to "read it anyway" would silently undo it.
func redactImage(ctx context.Context, raw []byte, filename string) ([]byte, error) {
	url := getEnvOrDefault("PRESIDIO_IMAGE_REDACTOR_URL", "http://localhost:5003/redact")

	var body bytes.Buffer
	writer := multipart.NewWriter(&body)
	part, err := writer.CreateFormFile("image", filename)
	if err != nil {
		return nil, fmt.Errorf("build form: %w", err)
	}
	if _, err := part.Write(raw); err != nil {
		return nil, fmt.Errorf("write image: %w", err)
	}
	if err := writer.WriteField("data", `{"color_fill":"0,0,0"}`); err != nil {
		return nil, fmt.Errorf("write field: %w", err)
	}
	if err := writer.Close(); err != nil {
		return nil, fmt.Errorf("close form: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, &body)
	if err != nil {
		return nil, fmt.Errorf("build request: %w", err)
	}
	req.Header.Set("Content-Type", writer.FormDataContentType())

	resp, err := redactorClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("redactor unreachable: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		return nil, fmt.Errorf("redactor returned %d", resp.StatusCode)
	}
	return io.ReadAll(resp.Body)
}

// readRedactedImage asks Gemini to transcribe an image that has already been redacted.
func readRedactedImage(ctx context.Context, redacted []byte, mimeType string) (string, error) {
	model := getEnvOrDefault("OCR_MODEL", "")
	key := getEnvOrDefault("GOOGLE_API_KEY", "")
	if model == "" || key == "" {
		return "", nil // OCR not configured: not an error, the text body still ingests
	}

	payload, err := json.Marshal(map[string]any{
		"contents": []any{map[string]any{"parts": []any{
			map[string]any{"text": ocrPrompt},
			map[string]any{"inline_data": map[string]string{
				"mime_type": mimeType,
				"data":      base64.StdEncoding.EncodeToString(redacted),
			}},
		}}},
		"generationConfig": map[string]any{"temperature": 0},
	})
	if err != nil {
		return "", fmt.Errorf("marshal request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost,
		fmt.Sprintf(geminiEndpoint, model), bytes.NewReader(payload))
	if err != nil {
		return "", fmt.Errorf("build request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-goog-api-key", key)

	resp, err := ocrClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("ocr request: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		return "", fmt.Errorf("ocr returned %d", resp.StatusCode)
	}

	var parsed struct {
		Candidates []struct {
			Content struct {
				Parts []struct {
					Text string `json:"text"`
				} `json:"parts"`
			} `json:"content"`
		} `json:"candidates"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&parsed); err != nil {
		return "", fmt.Errorf("decode ocr response: %w", err)
	}
	if len(parsed.Candidates) == 0 || len(parsed.Candidates[0].Content.Parts) == 0 {
		return "", nil
	}
	return strings.TrimSpace(parsed.Candidates[0].Content.Parts[0].Text), nil
}

// ocrAttachments returns transcribed text for every image attachment on the message.
//
// A failure on one attachment is logged and skipped rather than failing the message: an email
// whose screenshot could not be read is still worth ingesting for its body, and #84 made ingest
// failures retry, so failing here would loop the whole message over one unreadable image.
func ocrAttachments(ctx context.Context, srv *gmail.Service, msgID string, payload *gmail.MessagePart) string {
	if payload == nil {
		return ""
	}
	parts := imageAttachments(payload, ocrMaxBytes())
	if len(parts) == 0 {
		return ""
	}

	var transcripts []string
	for _, part := range parts {
		attachment, err := srv.Users.Messages.Attachments.
			Get("me", msgID, part.Body.AttachmentId).Context(ctx).Do()
		if err != nil {
			logOCRFailure(ctx, msgID, "fetch", err)
			continue
		}
		raw, err := base64.URLEncoding.DecodeString(attachment.Data)
		if err != nil {
			logOCRFailure(ctx, msgID, "decode", err)
			continue
		}

		redacted, err := redactImage(ctx, raw, part.Filename)
		if err != nil {
			// Not falling through to OCR on purpose — see redactImage's comment.
			logOCRFailure(ctx, msgID, "redact", err)
			continue
		}

		text, err := readRedactedImage(ctx, redacted, part.MimeType)
		if err != nil {
			logOCRFailure(ctx, msgID, "read", err)
			continue
		}
		if text != "" {
			transcripts = append(transcripts, text)
			writeAuditLog(ctx, "ocr_attachment",
				fmt.Sprintf("msg %s: %s redacted and read, %d chars", msgID, part.MimeType, len(text)), true)
		}
	}

	if len(transcripts) == 0 {
		return ""
	}
	return ocrMarker + strings.Join(transcripts, "\n\n")
}

func logOCRFailure(ctx context.Context, msgID, stage string, err error) {
	// The error is logged, never the attachment: a redactor failure means the image still holds
	// whatever PII it held.
	fmt.Printf("OCR %s failed for msg %s: %v\n", stage, msgID, err)
	writeAuditLog(ctx, "ocr_attachment", fmt.Sprintf("msg %s: %s failed: %v", msgID, stage, err), false)
}
