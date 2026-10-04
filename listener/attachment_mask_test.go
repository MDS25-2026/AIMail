package main

import (
	"context"
	"net/http"
	"strings"
	"testing"
	"unicode/utf8"
)

func TestChunkTextKeepsEveryCharacterAndRespectsTheLimit(t *testing.T) {
	text := strings.Repeat("a line of attachment text\n", 400) + strings.Repeat("x", 7000)
	chunks := chunkText(text, 3000)
	if strings.Join(chunks, "") != text {
		t.Fatal("chunking lost or reordered text")
	}
	for _, chunk := range chunks {
		if len(chunk) > 3000 {
			t.Fatalf("chunk of %d exceeds the limit", len(chunk))
		}
	}
}

func TestChunkTextNeverSplitsAMultiByteCharacter(t *testing.T) {
	text := strings.Repeat("发票金额", 2000) // one long line of three-byte runes
	for _, chunk := range chunkText(text, 3000) {
		if !utf8.ValidString(chunk) {
			t.Fatal("a chunk boundary split a character")
		}
	}
}

func TestAttachmentTextIsDroppedWhenNERIsUnavailable(t *testing.T) {
	// Pointing Presidio at a closed port is how maskText degrades to the regex floor.
	t.Setenv("PRESIDIO_ANALYZER_URL", "http://127.0.0.1:1/analyze")
	withSupabase(t, func(w http.ResponseWriter, _ *http.Request) {})
	masked, _, _ := maskAttachmentText(context.Background(), "m1", "Invoice for Aisyah Rahman")
	if masked != "" {
		t.Fatalf("degraded attachment text must be dropped, got %q", masked)
	}
}

func TestAnEmailAcrossAChunkBoundaryIsStillMasked(t *testing.T) {
	// The regex floor must see the whole text: cut first, and neither half matches.
	t.Setenv("PRESIDIO_ANALYZER_URL", "http://127.0.0.1:1/analyze")
	withSupabase(t, func(w http.ResponseWriter, _ *http.Request) {})
	text := strings.Repeat("a", nerChunkChars-10) + " john.doe@example.com and more"
	masked, emails, _, _ := maskText(context.Background(), text)
	if strings.Contains(masked, "john.doe") || strings.Contains(masked, "example.com") || emails != 1 {
		t.Fatalf("an address straddling the cut leaked: emails=%d", emails)
	}
}

func TestChunksCutAtWhitespaceSoWordsStayWhole(t *testing.T) {
	text := strings.Repeat("word ", 1000) // one long line
	for _, chunk := range chunkText(text, 3000) {
		if strings.HasSuffix(strings.TrimRight(chunk, " "), "wor") || strings.HasPrefix(chunk, "d ") {
			t.Fatal("a word was cut in half")
		}
	}
}
