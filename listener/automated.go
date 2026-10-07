package main

import (
	"regexp"
	"strings"

	"google.golang.org/api/gmail/v1"
)

// A sender that never reads replies (RFC 3834 section 2): answering it only feeds a loop.
var noReplySender = regexp.MustCompile(`(?i)(^|[<\s"])(no-?reply|do-?not-?reply|mailer-daemon|postmaster|bounces?)[@+._-]`)

// isAutomated reports mail no person wrote for a reply: mailing lists, bulk mail, auto-replies,
// bounces and no-reply senders. Holding replies never answer it (specs/features/holding-reply.md).
func isAutomated(headers []*gmail.MessagePartHeader) bool {
	precedence := strings.ToLower(strings.TrimSpace(headerValue(headers, "Precedence")))
	autoSubmitted := strings.ToLower(strings.TrimSpace(headerValue(headers, "Auto-Submitted")))
	return headerValue(headers, "List-Id") != "" ||
		headerValue(headers, "List-Unsubscribe") != "" ||
		precedence == "bulk" || precedence == "list" || precedence == "junk" ||
		(autoSubmitted != "" && autoSubmitted != "no") ||
		strings.TrimSpace(headerValue(headers, "Return-Path")) == "<>" ||
		noReplySender.MatchString(headerValue(headers, "From"))
}
