package main

import (
	"context"
	"fmt"
	"strings"
	"unicode/utf8"
)

// NER runs in pieces this size: one Presidio call answers well inside presidioClient's 5 s at this
// length, where a 20-page PDF's text in one call may not.
const nerChunkChars = 3000

// chunkText splits into pieces of at most max bytes, cutting at a line break where it can, else at
// the last whitespace, and only as a last resort mid-word (never mid-character). Words stay whole,
// so NER still sees each name intact.
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
			cut := cutPoint(line, max)
			chunks = append(chunks, line[:cut])
			line = line[cut:]
		}
		current.WriteString(line)
	}
	flush()
	return chunks
}

// cutPoint is the last whitespace at or before max, or failing that the last character boundary.
func cutPoint(line string, max int) int {
	if space := strings.LastIndexAny(line[:max], " \t"); space > 0 {
		return space + 1
	}
	cut := max
	for cut > 0 && !utf8.RuneStart(line[cut]) {
		cut-- // never split a multi-byte character: Chinese text is three bytes a rune
	}
	return cut
}

// maskAttachmentText masks attachment text like any other, and drops it entirely if NER was
// unavailable. A body without NER is quarantined; attachment text is optional, and is where full
// names, addresses and account holders are densest, so it is simply not stored.
func maskAttachmentText(ctx context.Context, msgID, text string, v *detailVault) (masked string, emails, phones int) {
	if text == "" {
		return "", 0, 0
	}
	// Masked into a copy: text that is dropped must not leave its details in the email's vault.
	scratch := v.fork()
	masked, emails, phones, degraded := maskText(ctx, text, scratch)
	if degraded {
		// Its own action name: the admin console counts these, and must not parse prose to do it.
		writeAuditLog(ctx, "drop_attachment_text",
			fmt.Sprintf("msg %s: attachment text dropped, NER masking unavailable", msgID), false)
		return "", 0, 0
	}
	*v = *scratch
	return masked, emails, phones
}
