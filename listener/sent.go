package main

// Replies the mailbox sent (specs/features/todo-page.md), for the to-do's waiting list. Masked like
// received mail and kept in sent_message, never messages, so nothing that drafts or lists received
// mail can mistake one for an email to answer. Losing one only loses a reminder, so a failure here
// is recorded and skipped: it must never hold up received mail.

import (
	"context"
	"errors"
	"log"
	"strings"
	"time"

	"google.golang.org/api/gmail/v1"
)

const (
	actionStoreSent   auditAction = "store_sent_message"
	reasonSentSkipped             = "sent_message_skipped"
	stageSentHistory              = "sent_history"
)

var errSentNotMasked = errors.New("sent message could not be fully masked")

// SentRow is a sent reply as stored: masked text only, and no recipient address.
type SentRow struct {
	UserID     string    `json:"user_id,omitempty"` // omitted (NULL) for the token.json mailbox
	GmailID    string    `json:"gmail_id"`
	ThreadID   string    `json:"thread_id,omitempty"`
	SentAt     time.Time `json:"sent_at"`
	Subject    string    `json:"subject"`
	BodyMasked string    `json:"body_masked"`
}

// sentSince lists what the mailbox sent after start. A failure costs reminders only, so it is
// recorded and the received mail goes on.
func sentSince(ctx context.Context, mb *mailbox, start uint64) []string {
	var ids []string
	call := mb.srv.Users.History.List("me").StartHistoryId(start).HistoryTypes("messageAdded").LabelId("SENT")
	err := call.Pages(ctx, func(page *gmail.ListHistoryResponse) error {
		for _, record := range page.History {
			for _, added := range record.MessagesAdded {
				if added.Message != nil {
					ids = append(ids, added.Message.Id)
				}
			}
		}
		return nil
	})
	if err != nil {
		writeAuditLog(ctx, mb.ownerID, actionStoreSent, auditFields{fieldStage: stageSentHistory,
			fieldErrorKind: errorKind(err)}, false)
		return nil
	}
	return ids
}

// ingestSent stores each sent reply; one that fails is recorded and skipped.
func ingestSent(ctx context.Context, mb *mailbox, ids []string) {
	for _, msgID := range ids {
		if err := ingestSentMessage(ctx, mb, msgID); err != nil {
			log.Printf("sent message %s not stored: %v", msgID, err)
			messageRef{ownerID: mb.ownerID, msgID: msgID}.audit(ctx, actionStoreSent,
				auditFields{fieldReason: reasonSentSkipped, fieldErrorKind: errorKind(err)}, false)
		}
	}
}

func ingestSentMessage(ctx context.Context, mb *mailbox, msgID string) error {
	msg, err := fetchMessage(ctx, mb.srv, messageRef{ownerID: mb.ownerID, msgID: msgID})
	if err != nil {
		return err
	}
	// Mail to yourself carries INBOX too and is already ingested as received mail; an automatic
	// reply (a holding reply among them) asks nothing of anyone.
	if msg.Payload == nil || !isOwnSentReply(msg) || isAutoReply(headerValue(msg.Payload.Headers, "Auto-Submitted")) {
		return nil
	}
	row, isMasked := maskSent(ctx, mb.ownerID, msg.Id, msg.ThreadId, msg.InternalDate,
		headerValue(msg.Payload.Headers, "Subject"), getBody(msg.Payload))
	if !isMasked {
		return errSentNotMasked
	}
	_, err = insertIgnoringDuplicates(ctx, "sent_message", "gmail_id", "gmail_id", row)
	return err
}

// isAutoReply reads an Auto-Submitted header (RFC 3834): anything but "no" was not written by a person.
func isAutoReply(autoSubmitted string) bool {
	value := strings.TrimSpace(autoSubmitted)
	return value != "" && !strings.EqualFold(value, "no")
}

// maskSent masks the subject and body; attachments are not read for a sent reply.
func maskSent(ctx context.Context, ownerID, gmailID, threadID string, internalDate int64, subject, body string) (SentRow, bool) {
	vault := newDetailVault()
	maskedBody, _, _, degradedBody := maskText(ctx, body, vault)
	maskedSubject, _, _, degradedSubject := maskText(ctx, subject, vault)
	if degradedBody || degradedSubject {
		return SentRow{}, false
	}
	return SentRow{UserID: ownerID, GmailID: gmailID, ThreadID: threadID,
		SentAt: time.UnixMilli(internalDate).UTC(), Subject: maskedSubject, BodyMasked: maskedBody}, true
}
