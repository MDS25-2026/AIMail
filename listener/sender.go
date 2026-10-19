package main

import (
	"net/mail"
	"time"

	"google.golang.org/api/gmail/v1"
)

// SenderFacts is what the headers say about a message's sender and thread, computed once by
// senderFacts and embedded in every messages row, so no write path can leave a column to its default.
type SenderFacts struct {
	FromAddr   string    `json:"from_addr"`          // kept unmasked on purpose: docs/decisions/shared.md, 2026-10-04
	ReplyTo    string    `json:"reply_to,omitempty"` // where an approved reply goes; shown to the approver
	ReceivedAt time.Time `json:"received_at"`
	// The sender's offset from UTC in minutes, from their Date header; null when it cannot be read.
	// A hint for "it's 11:40pm for them", never a reason to block (quiet-hours-send-later.md).
	SenderUTCOffsetMinutes *int `json:"sender_utc_offset_minutes"`
	SenderVerdict
	ThreadIdentity
}

// SenderVerdict is the part a quarantine release writes again: rows quarantined before it was
// stored hold the column defaults, which would read a spoof as a pass.
type SenderVerdict struct {
	AuthStatus  string `json:"auth_status"`
	IsAutomated bool   `json:"is_automated"` // never sent a holding reply (automated.go)
}

func receivedAt(msg *gmail.Message) time.Time {
	if msg.InternalDate > 0 {
		return time.UnixMilli(msg.InternalDate).UTC()
	}
	return time.Now().UTC()
}

// senderFacts needs msg.Payload; callers have already dropped messages without one.
func senderFacts(msg *gmail.Message) SenderFacts {
	headers := msg.Payload.Headers
	return SenderFacts{
		FromAddr:               headerValue(headers, "From"),
		ReplyTo:                headerValue(headers, "Reply-To"),
		ReceivedAt:             receivedAt(msg),
		SenderUTCOffsetMinutes: utcOffsetMinutes(headerValue(headers, "Date")),
		SenderVerdict:          senderVerdict(headers, msg.LabelIds),
		ThreadIdentity:         threadIdentity(msg),
	}
}

func senderVerdict(headers []*gmail.MessagePartHeader, labels []string) SenderVerdict {
	return SenderVerdict{AuthStatus: parseAuthStatus(headers), IsAutomated: isAutomated(headers, labels)}
}

// utcOffsetMinutes reads the zone of an RFC 5322 date: "Tue, 7 Oct 2026 23:40:00 +0800" gives 480.
func utcOffsetMinutes(date string) *int {
	parsed, err := mail.ParseDate(date)
	if err != nil {
		return nil
	}
	_, seconds := parsed.Zone()
	minutes := seconds / 60
	return &minutes
}
