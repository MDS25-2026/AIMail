package main

import (
	"regexp"
	"slices"
	"strings"

	"google.golang.org/api/gmail/v1"
)

// A sender that never reads replies (RFC 3834 section 2): answering it only feeds a loop.
var noReplySender = regexp.MustCompile(`(?i)(^|[<\s"])(no-?reply|do-?not-?reply|mailer-daemon|postmaster|bounces?)[@+._-]`)

// Gmail's own tabs for mail no person wrote to you: newsletters and notifications (Milanote's carried
// none of the headers below, so it was drafted for). Primary mail has none of these labels.
var automatedCategories = []string{"CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL", "CATEGORY_UPDATES", "CATEGORY_FORUMS"}

// isAutomated reports mail no person wrote for a reply: mailing lists, bulk mail, auto-replies,
// bounces, no-reply senders and Gmail's non-primary tabs. It gets no holding reply
// (specs/features/holding-reply.md) and no automatic draft.
func isAutomated(headers []*gmail.MessagePartHeader, labels []string) bool {
	if slices.ContainsFunc(labels, func(label string) bool { return slices.Contains(automatedCategories, label) }) {
		return true
	}
	precedence := strings.ToLower(strings.TrimSpace(headerValue(headers, "Precedence")))
	autoSubmitted := strings.ToLower(strings.TrimSpace(headerValue(headers, "Auto-Submitted")))
	return headerValue(headers, "List-Id") != "" ||
		headerValue(headers, "List-Unsubscribe") != "" ||
		precedence == "bulk" || precedence == "list" || precedence == "junk" ||
		(autoSubmitted != "" && autoSubmitted != "no") ||
		strings.TrimSpace(headerValue(headers, "Return-Path")) == "<>" ||
		noReplySender.MatchString(headerValue(headers, "From"))
}
