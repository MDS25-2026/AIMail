package main

// Signatures, faces and stamps are not text, so the reader's word-by-word redaction cannot box them
// out (specs/features/signature-detection.md). For an owner who chose checked scans, a vision model
// on this machine is asked about each image before it goes to Gemini, and any doubt keeps it here.
// Measured on synthetic scans, it still misses about 1 in 10; the settings card says so.

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"
)

const (
	markPrompt = "Look at this document image. Answer three questions about what is drawn on it, not printed text. " +
		"signature: is there any handwritten mark, scribble, signature or initials? " +
		"face: is there a photo or drawing of a person? " +
		"stamp: is there a rubber stamp, seal or circular or boxed coloured marking? " +
		`Reply only with JSON {"signature": true|false, "face": true|false, "stamp": true|false}.`
	defaultLocalLLMURL = "http://localhost:11434"
	generatePath       = "/api/generate"

	reasonMarkFound   = "signature_face_or_stamp"
	reasonNoMarkCheck = "no_mark_check"
)

// A cold start (the model unloaded after idling) measured 44.5 s; warm answers take 1 to 7 s.
var markClient = &http.Client{Timeout: 60 * time.Second}

// clearOfMarks says, per image, whether the local model found it free of signatures, faces and
// stamps. No model configured, no answer, or anything but three clear noes counts as not clear.
func clearOfMarks(ctx context.Context, ref messageRef, images []redactedImage) []bool {
	clear := make([]bool, len(images))
	model := getEnvOrDefault("LOCAL_VISION_MODEL", "")
	if model == "" {
		auditWithheld(ctx, ref, reasonNoMarkCheck, len(images), false)
		return clear
	}
	found := 0
	for i, img := range images {
		hasMark, err := hasMark(ctx, model, img.Data)
		if err != nil {
			// The rest stay local unasked: one stuck call per image would hold the callback (#86).
			logOCRFailure(ctx, ref, stageMarkCheck, err)
			auditWithheld(ctx, ref, reasonNoMarkCheck, len(images)-i, false)
			break
		}
		clear[i] = !hasMark
		if hasMark {
			found++
		}
	}
	auditWithheld(ctx, ref, reasonMarkFound, found, true)
	return clear
}

func auditWithheld(ctx context.Context, ref messageRef, reason string, count int, success bool) {
	if count == 0 {
		return
	}
	// fieldWithheld is the key the admin console sums into withheld pages.
	ref.audit(ctx, actionSkipCloudOCR, auditFields{fieldReason: reason, fieldWithheld: count}, success)
}

// hasMark asks the local model about one base64 PNG. An answer it cannot read counts as a mark.
func hasMark(ctx context.Context, model, encoded string) (bool, error) {
	payload, err := json.Marshal(map[string]any{
		"model": model, "prompt": markPrompt, "images": []string{encoded},
		"stream": false, "think": false, "format": "json",
		"options": map[string]any{"temperature": 0},
	})
	if err != nil {
		return false, fmt.Errorf("marshal request: %w", err)
	}
	url := strings.TrimRight(getEnvOrDefault("LOCAL_LLM_URL", defaultLocalLLMURL), "/") + generatePath
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(payload))
	if err != nil {
		return false, fmt.Errorf("build request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := markClient.Do(req)
	if err != nil {
		return false, fmt.Errorf("local model unreachable: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		return false, fmt.Errorf("local model returned %d", resp.StatusCode)
	}
	var reply struct {
		Response string `json:"response"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&reply); err != nil {
		return false, fmt.Errorf("decode local model reply: %w", err)
	}
	return !allNo(reply.Response), nil
}

// allNo is true only for an answer naming all three marks, each false.
func allNo(answer string) bool {
	var verdict struct {
		Signature, Face, Stamp *bool
	}
	if err := json.Unmarshal([]byte(answer), &verdict); err != nil {
		return false
	}
	for _, seen := range []*bool{verdict.Signature, verdict.Face, verdict.Stamp} {
		if seen == nil || *seen {
			return false
		}
	}
	return true
}
