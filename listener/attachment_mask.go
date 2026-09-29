package main

import (
	"context"
	"fmt"
	"strings"
	"unicode/utf8"
)

// Presidio answers a short body well inside presidioClient's 5 s; a 20-page PDF's text may not.
// Masking attachment text in pieces this size keeps every call short.
const attachmentMaskChunkChars = 3000

// chunkText splits at line breaks into pieces of at most max characters (a single longer line is
// cut where it must be), so no sentence is split unless it has to be.
func chunkText(text string, max int) []string {
	var chunks []string
	var current strings.Builder
	flush := func() {
		if current.Len() > 0 {
			chunks = append(chunks, current.String())
			current.Reset()
		}
	}
	for _, line := range strings.SplitAfter(text, "\n") {
		if current.Len()+len(line) > max {
			flush()
		}
		for len(line) > max {
			cut := max
			for cut > 0 && !utf8.RuneStart(line[cut]) {
				cut-- // never split a multi-byte character: Chinese text is three bytes a rune
			}
			chunks = append(chunks, line[:cut])
			line = line[cut:]
		}
		current.WriteString(line)
	}
	flush()
	return chunks
}

// maskAttachmentText masks attachment text on its own, and drops it entirely if any piece fell
// back to the regex floor. A body without NER masking is an accepted degradation; attachment text
// is not, because it is where full names, addresses and account holders are densest, and it is
// optional: the email still ingests on its body.
func maskAttachmentText(ctx context.Context, msgID, text string) (masked string, emails, phones int) {
	if text == "" {
		return "", 0, 0
	}
	var pieces []string
	for _, chunk := range chunkText(text, attachmentMaskChunkChars) {
		piece, e, p, degraded := maskText(ctx, chunk)
		if degraded {
			// Its own action name: the admin console counts these, and must not parse prose to do it.
			writeAuditLog(ctx, "drop_attachment_text",
				fmt.Sprintf("msg %s: attachment text dropped, NER masking unavailable", msgID), false)
			return "", 0, 0
		}
		pieces = append(pieces, piece)
		emails += e
		phones += p
	}
	return strings.Join(pieces, ""), emails, phones
}
