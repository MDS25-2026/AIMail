package main

// Audit rows (specs/context/backbone-contracts.md, "Audit rows"): detail is a compact JSON object with
// sorted keys, never prose, an email address or body text, and user_id names the owner it was for.

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"strings"
	"time"

	"golang.org/x/oauth2"
	"google.golang.org/api/googleapi"
)

// auditAction is the shared action list; the admin console counts rows by these exact names.
type auditAction string

const (
	actionQuarantineMessage  auditAction = "quarantine_message"
	actionRemaskMessage      auditAction = "remask_message"
	actionDropAttachmentText auditAction = "drop_attachment_text"
	actionReadAttachment     auditAction = "read_attachment"
	actionOCRAttachment      auditAction = "ocr_attachment"
	actionSkipCloudOCR       auditAction = "skip_cloud_ocr"
	actionStartMailbox       auditAction = "start_mailbox"
	actionStopMailbox        auditAction = "stop_mailbox"
	actionSetupWatch         auditAction = "setup_watch"
	actionRenewWatch         auditAction = "renew_watch"
	actionIngestAbandoned    auditAction = "ingest_abandoned"
	actionIngestSkipped      auditAction = "ingest_skipped"
	actionFetchHistory       auditAction = "fetch_history"
	actionFetchMessage       auditAction = "fetch_message"
	actionStoreMessage       auditAction = "store_message"
)

// Detail keys. Values are ids, counts and the constants below: nothing that can carry content.
const (
	fieldGmailMessageID = "gmail_message_id"
	fieldHistoryID      = "history_id"
	fieldReason         = "reason"
	fieldStage          = "stage"
	fieldErrorKind      = "error_kind"
	fieldAttempts       = "attempts"
	fieldEmailsMasked   = "emails_masked"
	fieldPhonesMasked   = "phones_masked"
	fieldMimeType       = "mime_type"
	fieldPages          = "pages"
	fieldImagesSent     = "images_sent"
	fieldWithheld       = "withheld"
	fieldUnread         = "unread"
	fieldOversize       = "oversize"
	fieldChars          = "chars"
	fieldImagesSkipped  = "images_skipped"
	fieldMaskingStatus  = "masking_status"
	fieldUnsupported    = "unsupported"
)

// Reasons are snake_case codes from this fixed set, so the admin console can count them.
const (
	reasonNERUnavailable    = "ner_unavailable"
	reasonGoneFromGmail     = "gone_from_gmail"
	reasonFetchFailed       = "fetch_failed"
	reasonMaskingIncomplete = "masking_incomplete"
	reasonStoreFailed       = "store_failed"
	reasonReleased          = "released"
	reasonNoPayload         = "no_payload"
	reasonOverSizeCap       = "over_size_cap"
	reasonUnsupportedType   = "unsupported_type"
	reasonTypeMismatch      = "type_mismatch"
	reasonDisconnected      = "disconnected"
	reasonHistoryUnusable   = "history_unusable"
	reasonTooManyAttempts   = "too_many_attempts"
	reasonPermanentFailure  = "permanent_failure"
)

// Stages name the step that failed.
const (
	stageFetch          = "fetch"
	stageDecode         = "decode"
	stageReadLocally    = "read_locally"
	stageDecodeRedacted = "decode_redacted_image"
	stageOCR            = "ocr"
	stageStore          = "store"
	stageProfile        = "profile"
	stageWatch          = "watch"
	stageList           = "list"
	stageStart          = "start"
)

// Error kinds: an error's text can quote a Gmail reply or an address, so only its kind is kept.
const (
	errKindTimeout      = "timeout"
	errKindCanceled     = "canceled"
	errKindOAuthRefused = "oauth_refused"
	errKindRowRejected  = "row_rejected"
	errKindGmailPrefix  = "gmail_http_"
	errKindOther        = "other"
)

type auditFields map[string]any

// AuditLogEntry is one audit_log row.
type AuditLogEntry struct {
	Action    auditAction `json:"action"`
	Detail    string      `json:"detail"`
	Success   bool        `json:"success"`
	UserID    string      `json:"user_id,omitempty"` // the token.json mailbox has no owner
	CreatedAt time.Time   `json:"created_at"`
}

// writeAuditLog is best effort: a failure is logged locally and never blocks the pipeline.
func writeAuditLog(ctx context.Context, ownerID string, action auditAction, fields auditFields, success bool) {
	entry := AuditLogEntry{
		Action:    action,
		Detail:    encodeDetail(fields),
		Success:   success,
		UserID:    ownerID,
		CreatedAt: time.Now().UTC(),
	}
	if err := supabaseInsert(ctx, "audit_log", entry, ""); err != nil {
		log.Printf("audit log write failed: %v", err)
	}
}

// encodeDetail matches the backend's json.dumps(sort_keys=True, separators=(",", ":")): encoding/json
// sorts map keys, and HTML escaping is off because Python does not escape <, > or &.
func encodeDetail(fields auditFields) string {
	if fields == nil {
		fields = auditFields{}
	}
	var out bytes.Buffer
	encoder := json.NewEncoder(&out)
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(fields); err != nil {
		return "{}" // only a value json cannot encode gets here; the fields are ids and counts
	}
	return strings.TrimSuffix(out.String(), "\n")
}

// errorKind names an error without its text.
func errorKind(err error) string {
	var apiErr *googleapi.Error
	var refused *oauth2.RetrieveError
	switch {
	case errors.Is(err, context.DeadlineExceeded):
		return errKindTimeout
	case errors.Is(err, context.Canceled):
		return errKindCanceled
	case errors.Is(err, errRowRejected):
		return errKindRowRejected
	case errors.As(err, &refused):
		return errKindOAuthRefused
	case errors.As(err, &apiErr):
		return fmt.Sprintf("%s%d", errKindGmailPrefix, apiErr.Code)
	}
	return errKindOther
}

// messageRef names one message of one mailbox, so every audit row about it carries both.
type messageRef struct {
	ownerID string
	msgID   string
}

func (m messageRef) audit(ctx context.Context, action auditAction, fields auditFields, success bool) {
	if fields == nil {
		fields = auditFields{}
	}
	fields[fieldGmailMessageID] = m.msgID
	writeAuditLog(ctx, m.ownerID, action, fields, success)
}

// auditFailure records a failed step with the error's kind only.
func (m messageRef) auditFailure(ctx context.Context, action auditAction, stage string, err error) {
	m.audit(ctx, action, auditFields{fieldStage: stage, fieldErrorKind: errorKind(err)}, false)
}
