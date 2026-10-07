package main

import (
	"strings"

	"google.golang.org/api/gmail/v1"
)

// ThreadIdentity is what a reply needs to join this message's thread (RFC 5322 §3.6.4, and
// Gmail's own rule that a reply carry the threadId). Identifiers, not content: stored unmasked,
// because a Message-ID looks like an email address and masking it would break threading.
type ThreadIdentity struct {
	ThreadID        string `json:"thread_id,omitempty"`
	RFC822MessageID string `json:"rfc822_message_id,omitempty"`
	ThreadRefs      string `json:"thread_refs,omitempty"`
}

func threadIdentity(msg *gmail.Message) ThreadIdentity {
	identity := ThreadIdentity{ThreadID: msg.ThreadId}
	if msg.Payload == nil {
		return identity
	}
	identity.RFC822MessageID = headerValue(msg.Payload.Headers, "Message-ID")
	identity.ThreadRefs = headerValue(msg.Payload.Headers, "References")
	return identity
}

// headerValue matches case-insensitively: senders write Message-ID, Message-Id and MESSAGE-ID.
func headerValue(headers []*gmail.MessagePartHeader, name string) string {
	for _, header := range headers {
		if strings.EqualFold(header.Name, name) {
			return header.Value
		}
	}
	return ""
}

// parseAuthStatus checks Authentication-Results headers for SPF, DKIM, or DMARC failures (#148).
func parseAuthStatus(headers []*gmail.MessagePartHeader) string {
	for _, h := range headers {
		if strings.EqualFold(h.Name, "Authentication-Results") {
			val := strings.ToLower(h.Value)
			if strings.Contains(val, "spf=fail") || strings.Contains(val, "dkim=fail") || strings.Contains(val, "dmarc=fail") {
				return "spoof_detected"
			}
		}
	}
	return "pass"
}

