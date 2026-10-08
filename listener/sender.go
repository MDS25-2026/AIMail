package main

import (
	"time"

	"google.golang.org/api/gmail/v1"
)

// SenderFacts is what the headers say about a message's sender and thread, computed once by
// senderFacts and embedded in every messages row, so no write path can leave a column to its default.
type SenderFacts struct {
	FromAddr   string    `json:"from_addr"`          // kept unmasked on purpose: docs/decisions/shared.md, 2026-10-04
	ReplyTo    string    `json:"reply_to,omitempty"` // where an approved reply goes; shown to the approver
	ReceivedAt time.Time `json:"received_at"`
	SenderVerdict
	ThreadIdentity
}

// SenderVerdict is the part a quarantine release writes again: rows quarantined before it was
// stored hold the column defaults, which would read a spoof as a pass.
type SenderVerdict struct {
	AuthStatus  string `json:"auth_status"`
	IsAutomated bool   `json:"is_automated"` // never sent a holding reply (automated.go)
}

// senderFacts needs msg.Payload; callers have already dropped messages without one.
func senderFacts(msg *gmail.Message) SenderFacts {
	headers := msg.Payload.Headers
	return SenderFacts{
		FromAddr:       headerValue(headers, "From"),
		ReplyTo:        headerValue(headers, "Reply-To"),
		ReceivedAt:     time.Now().UTC(),
		SenderVerdict:  senderVerdict(headers),
		ThreadIdentity: threadIdentity(msg),
	}
}

func senderVerdict(headers []*gmail.MessagePartHeader) SenderVerdict {
	return SenderVerdict{AuthStatus: parseAuthStatus(headers), IsAutomated: isAutomated(headers)}
}
