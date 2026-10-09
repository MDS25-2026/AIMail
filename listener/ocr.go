package main

// Attachment reading (#82, extended to documents and scans).
//
// The ordering here is the whole point. Every attachment goes to the local attachment reader
// (listener/attachment-reader) first. Documents with text come back as text and are masked below
// like any body text, never touching a model. Images and scanned pages come back redacted, and
// only if the reader's OCR could read them confidently and found no PII left after redacting.
// Only those redacted images reach Gemini, and never for an owner in Private mode (privatemode.go). That keeps mask-before-transit true for attachments,
// which no cloud-OCR-first design can: reading an image is what finds the PII in it.

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"mime/multipart"
	"net/http"
	"path"
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

	ocrMarker = "\n\n--- text from attachments ---\n"

	pdfMime         = "application/pdf"
	zipMime         = "application/zip"
	octetStreamMime = "application/octet-stream"
	docxMime        = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
	xlsxMime        = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

// Reading and OCR are both slow enough to need generous deadlines, and both are bounded so a
// stuck call cannot hold the Pub/Sub receive callback open (the same failure as #86). The reader
// runs two local OCR passes per scanned page, up to its 20-page cap.
var (
	readerClient = &http.Client{Timeout: 180 * time.Second}
	ocrClient    = &http.Client{Timeout: 90 * time.Second}
)

// readerResult is the attachment reader's reply: local text, and redacted images that passed both
// of its gates. SkippedPages were withheld on this machine and never read remotely.
type readerResult struct {
	Text         string          `json:"text"`
	Images       []redactedImage `json:"images"`
	SkippedPages int             `json:"skipped_pages"`
	Pages        int             `json:"pages"`
	UnreadPages  int             `json:"unread_pages"` // past the page cap or the reader's time budget
}

func ocrMaxBytes() int64 {
	size, err := strconv.ParseInt(getEnvOrDefault("OCR_MAX_ATTACHMENT_BYTES", "5000000"), 10, 64)
	if err != nil || size <= 0 {
		return 5_000_000
	}
	return size
}

func isReadableAttachment(mimeType string) bool {
	switch mimeType {
	case pdfMime, docxMime, xlsxMime:
		return true
	}
	return strings.HasPrefix(mimeType, "image/")
}

// isCandidateAttachment is worth downloading: a type the reader handles, or one the sender's mail client
// left unlabelled, which sniffing may still identify.
func isCandidateAttachment(mimeType string) bool {
	return isReadableAttachment(mimeType) || mimeType == octetStreamMime
}

// unsupportedAttachments counts attachments that are never read because of their type, so the loss is
// recorded instead of silent.
func unsupportedAttachments(part *gmail.MessagePart) int {
	count := 0
	if part.Body != nil && part.Body.AttachmentId != "" && !isCandidateAttachment(part.MimeType) {
		count++
	}
	for _, sub := range part.Parts {
		count += unsupportedAttachments(sub)
	}
	return count
}

// effectiveType is the type the bytes really are, when the reader handles it. The declared type is the
// sender's claim: a file labelled PDF that is not one is refused rather than handed to a parser, and an
// unlabelled one is read when its bytes (or, for Office files, its extension) say what it is.
func effectiveType(declared, filename string, raw []byte) (string, bool) {
	sniffed, _, _ := strings.Cut(http.DetectContentType(raw), ";")
	isImage := strings.HasPrefix(sniffed, "image/")
	switch {
	case declared == pdfMime:
		return pdfMime, sniffed == pdfMime
	case strings.HasPrefix(declared, "image/") && isImage:
		return sniffed, true
	case strings.HasPrefix(declared, "image/"):
		// HEIC and TIFF are images Go cannot sniff: trust the label unless the bytes say otherwise.
		return declared, sniffed == octetStreamMime
	case declared == docxMime || declared == xlsxMime:
		return declared, sniffed == zipMime
	case declared == octetStreamMime && (sniffed == pdfMime || isImage):
		return sniffed, true
	case declared == octetStreamMime && sniffed == zipMime:
		return officeTypeByExtension(filename)
	}
	return "", false
}

func officeTypeByExtension(filename string) (string, bool) {
	switch strings.ToLower(path.Ext(filename)) {
	case ".docx":
		return docxMime, true
	case ".xlsx":
		return xlsxMime, true
	}
	return "", false
}

// oversizeAttachments counts readable attachments skipped for size, so the loss is recorded.
func oversizeAttachments(part *gmail.MessagePart, max int64) int {
	count := 0
	if isCandidateAttachment(part.MimeType) && part.Body != nil && part.Body.AttachmentId != "" &&
		part.Body.Size > max {
		count++
	}
	for _, sub := range part.Parts {
		count += oversizeAttachments(sub, max)
	}
	return count
}

// readableAttachments walks the MIME tree for attachments the reader handles, carrying an
// attachment id and within the size cap.
func readableAttachments(part *gmail.MessagePart, max int64) []*gmail.MessagePart {
	var found []*gmail.MessagePart
	if isCandidateAttachment(part.MimeType) &&
		part.Body != nil && part.Body.AttachmentId != "" && part.Body.Size <= max {
		found = append(found, part)
	}
	for _, sub := range part.Parts {
		found = append(found, readableAttachments(sub, max)...)
	}
	return found
}

type redactedImage struct {
	MimeType string `json:"mime_type"`
	Data     string `json:"data"`
}

// readLocally sends an attachment to the local reader. An error here must fail the attachment
// rather than fall through to OCR: sending an unread, unredacted image onward is the one outcome
// this design exists to prevent. The file name is deliberately not sent; names carry PII.
func readLocally(ctx context.Context, raw []byte, mimeType string) (readerResult, error) {
	url := getEnvOrDefault("ATTACHMENT_READER_URL", "http://localhost:5003/read")

	var body bytes.Buffer
	writer := multipart.NewWriter(&body)
	part, err := writer.CreateFormFile("file", "attachment")
	if err != nil {
		return readerResult{}, fmt.Errorf("build form: %w", err)
	}
	if _, err := part.Write(raw); err != nil {
		return readerResult{}, fmt.Errorf("write attachment: %w", err)
	}
	if err := writer.WriteField("mime_type", mimeType); err != nil {
		return readerResult{}, fmt.Errorf("write field: %w", err)
	}
	if err := writer.Close(); err != nil {
		return readerResult{}, fmt.Errorf("close form: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, &body)
	if err != nil {
		return readerResult{}, fmt.Errorf("build request: %w", err)
	}
	req.Header.Set("Content-Type", writer.FormDataContentType())

	resp, err := readerClient.Do(req)
	if err != nil {
		return readerResult{}, fmt.Errorf("attachment reader unreachable: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		return readerResult{}, fmt.Errorf("attachment reader returned %d", resp.StatusCode)
	}
	var result readerResult
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return readerResult{}, fmt.Errorf("decode reader reply: %w", err)
	}
	return result, nil
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

// ocrAttachments returns the text of every readable attachment on the message.
//
// A failure on one attachment is logged and skipped rather than failing the message: an email
// whose attachment could not be read is still worth ingesting for its body, and #84 made ingest
// failures retry, so failing here would loop the whole message over one unreadable file.
func ocrAttachments(ctx context.Context, srv *gmail.Service, ref messageRef, payload *gmail.MessagePart) string {
	if payload == nil {
		return ""
	}
	if skipped := oversizeAttachments(payload, ocrMaxBytes()); skipped > 0 {
		ref.audit(ctx, actionReadAttachment, auditFields{fieldReason: reasonOverSizeCap, fieldOversize: skipped}, false)
	}
	if unsupported := unsupportedAttachments(payload); unsupported > 0 {
		ref.audit(ctx, actionReadAttachment, auditFields{fieldReason: reasonUnsupportedType, fieldUnsupported: unsupported}, false)
	}
	parts := readableAttachments(payload, ocrMaxBytes())
	if len(parts) == 0 {
		return ""
	}
	cloudRefusal := cloudOCRRefusal(ctx, ref.ownerID) // once per message, not per attachment
	var texts []string
	for _, part := range parts {
		if text := readAttachment(ctx, srv, ref, part, cloudRefusal); text != "" {
			texts = append(texts, text)
		}
	}
	if len(texts) == 0 {
		return ""
	}
	return ocrMarker + strings.Join(texts, "\n\n")
}

// readAttachment reads one attachment; cloudRefusal, when set, keeps its redacted images from Gemini.
func readAttachment(ctx context.Context, srv *gmail.Service, ref messageRef, part *gmail.MessagePart, cloudRefusal string) string {
	attachment, err := srv.Users.Messages.Attachments.
		Get("me", ref.msgID, part.Body.AttachmentId).Context(ctx).Do()
	if err != nil {
		logOCRFailure(ctx, ref, stageFetch, err)
		return ""
	}
	raw, err := base64.URLEncoding.DecodeString(attachment.Data)
	if err != nil {
		logOCRFailure(ctx, ref, stageDecode, err)
		return ""
	}
	mimeType, isReadable := effectiveType(part.MimeType, part.Filename, raw)
	if !isReadable {
		ref.audit(ctx, actionReadAttachment, auditFields{fieldReason: reasonTypeMismatch, fieldMimeType: part.MimeType}, false)
		return ""
	}
	result, err := readLocally(ctx, raw, mimeType)
	if err != nil {
		// Not falling through to OCR on purpose: see readLocally's comment.
		logOCRFailure(ctx, ref, stageReadLocally, err)
		return ""
	}

	imageTexts, sent := transcribeImages(ctx, ref, result.Images, cloudRefusal)
	text := strings.TrimSpace(strings.Join(append([]string{result.Text}, imageTexts...), "\n\n"))
	// The admin console counts withheld and unread pages from these keys.
	ref.audit(ctx, actionReadAttachment, auditFields{fieldMimeType: mimeType, fieldPages: result.Pages,
		fieldImagesSent: sent, fieldWithheld: result.SkippedPages, fieldUnread: result.UnreadPages,
		fieldChars: len(text)}, true)
	return text
}

// transcribeImages sends the redacted images to Gemini unless the owner's choice refuses it. A
// refused image is not read at all, like attachment text without NER: its text is unavailable.
func transcribeImages(ctx context.Context, ref messageRef, images []redactedImage, cloudRefusal string) ([]string, int) {
	if len(images) == 0 {
		return nil, 0
	}
	if cloudRefusal != "" {
		ref.audit(ctx, actionSkipCloudOCR, auditFields{fieldReason: cloudRefusal, fieldImagesSkipped: len(images)},
			cloudRefusal == reasonPrivateMode)
		return nil, 0
	}
	texts := make([]string, 0, len(images))
	for _, img := range images {
		texts = append(texts, transcribe(ctx, ref, img.Data, img.MimeType))
	}
	return texts, len(images)
}

// transcribe OCRs one image the reader has already redacted and cleared.
func transcribe(ctx context.Context, ref messageRef, encoded, mimeType string) string {
	redacted, err := base64.StdEncoding.DecodeString(encoded)
	if err != nil {
		logOCRFailure(ctx, ref, stageDecodeRedacted, err)
		return ""
	}
	text, err := readRedactedImage(ctx, redacted, mimeType)
	if err != nil {
		logOCRFailure(ctx, ref, stageOCR, err)
		return ""
	}
	return text
}

func logOCRFailure(ctx context.Context, ref messageRef, stage string, err error) {
	// The error is logged, never the attachment: a reader failure means the file still holds
	// whatever PII it held.
	fmt.Printf("OCR %s failed for msg %s: %v\n", stage, ref.msgID, err)
	ref.auditFailure(ctx, actionOCRAttachment, stage, err)
}
