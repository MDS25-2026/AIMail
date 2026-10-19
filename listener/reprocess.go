package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/url"
	"time"

	"google.golang.org/api/gmail/v1"
)

// Gmail allows about 250 quota units a second per user; a full message read costs 5, and each email
// may also read its attachments. A short pause keeps a big mailbox well under that.
const reprocessPause = 200 * time.Millisecond

// Reasons an email is left as it is. Only counts and ids are printed, never content.
const (
	skipReplied       = "replied or sent"
	skipNotComplete   = "quarantined or abandoned"
	skipPastRetention = "past retention (body already cleared)"
	skipSendWaiting   = "a reply is waiting to send"
	skipClaimActive   = "actively claimed by a drafting worker"
	skipGone          = "no longer in Gmail"
	skipNotMasked     = "could not be fully masked now"
	skipFetchFailed   = "Gmail could not be read"
)

type reprocessRow struct {
	ID                     string  `json:"id"`
	GmailMessageID         string  `json:"gmail_message_id"`
	SentAt                 *string `json:"sent_at"`
	MaskingStatus          string  `json:"masking_status"`
	HasBody                bool    `json:"has_body"`
	HasDraft               bool    `json:"has_draft"`
	GenerationClaimedUntil *string `json:"generation_claimed_until"`
}

// reprocessPatch stores the new extraction and clears what was written in the old numbering: masking
// again renumbers the hidden details, so the old summary, items and draft would name the wrong people.
// Category goes too, so the worker labels the new text. The worker drafts the email again.
// Derived state (SLA, deadline, embeddings, importance, critic attempts, draft tone) is also reset (M21).
type reprocessPatch struct {
	MaskedContent
	AISummary          string           `json:"ai_summary"`
	DraftReply         string           `json:"draft_reply"`
	DraftShown         *string          `json:"draft_shown"`
	ActionItems        []string         `json:"action_items"`
	CriticConfidence   *float64         `json:"critic_confidence"`
	CriticChecks       *json.RawMessage `json:"critic_checks"`
	NeedsHumanReview   *bool            `json:"needs_human_review"`
	GeneratedAt        *string          `json:"generated_at"`
	RagSources         *json.RawMessage `json:"rag_sources"`
	GenerationAttempts int              `json:"generation_attempts"`
	Category           *string          `json:"category"`
	CategoryConfidence *float64         `json:"category_confidence"`
	// Normalised again from the new text (specs/features/normalisation-v2.md).
	Language  *string `json:"language"`
	SubjectEn *string `json:"subject_en"`
	OwnTextEn *string `json:"own_text_en"`
	// Derived state reset
	SlaPriority    SLAPriority `json:"sla_priority"`
	DeadlineAt     *string     `json:"deadline_at"`
	Embedding      *string     `json:"embedding"`
	Importance     *string     `json:"importance"`
	CriticAttempts int         `json:"critic_attempts"`
	DraftTone      *string     `json:"draft_tone"`
}

// runReprocess re-reads stored emails from Gmail with today's extraction (specs/features/readable-emails.md).
// Without --write it only counts: what it would change, and why the rest are skipped.
func runReprocess(ctx context.Context, args []string) error {
	flags := flag.NewFlagSet("reprocess", flag.ContinueOnError)
	isWrite := flags.Bool("write", false, "store the result (the default only counts)")
	if err := flags.Parse(args); err != nil {
		return err
	}
	rows, err := loadConnections(ctx)
	if err != nil {
		return fmt.Errorf("load connections: %w", err)
	}
	totals := map[string]int{}
	for _, connection := range rows {
		if err := reprocessMailbox(ctx, connection, *isWrite, totals); err != nil {
			log.Printf("mailbox of user %s not reprocessed: %v", connection.UserID, err)
		}
	}
	printTotals("reprocess", totals, *isWrite)
	return nil
}

func reprocessMailbox(ctx context.Context, connection connectionRow, isWrite bool, totals map[string]int) error {
	candidates, err := reprocessCandidates(ctx, connection.UserID, totals)
	if err != nil {
		return err
	}
	if !isWrite {
		totals["would change"] += len(candidates)
		for _, row := range candidates {
			if row.HasDraft {
				totals["would change: unsent draft redrafted"]++
			}
		}
		return nil
	}
	srv, err := connectionService(ctx, connection)
	if err != nil {
		return fmt.Errorf("gmail: %w", err)
	}
	if !presidioHealthy(ctx) {
		return fmt.Errorf("presidio is not answering; nothing was changed")
	}
	for _, row := range candidates {
		totals[reprocessOne(ctx, connection.UserID, row, srv)]++
	}
	return nil
}

// reprocessCandidates is every stored email of this owner that may be re-read, counting the others.
// It paginates in batches of 1000 to avoid silent truncations on large mailboxes (M22).
func reprocessCandidates(ctx context.Context, ownerID string, totals map[string]int) ([]reprocessRow, error) {
	var raw []struct {
		reprocessRow
		Body  *string `json:"has_body"`
		Draft *string `json:"has_draft"`
	}
	const batchSize = 1000
	offset := 0
	for {
		query := fmt.Sprintf("select=id,gmail_message_id,sent_at,masking_status,has_body:body_masked,has_draft:draft_reply,generation_claimed_until&%s&order=id.asc&limit=%d&offset=%d",
			ownerFilter(ownerID), batchSize, offset)
		body, err := supabaseGet(ctx, "messages", query)
		if err != nil {
			return nil, err
		}
		var batch []struct {
			reprocessRow
			Body  *string `json:"has_body"`
			Draft *string `json:"has_draft"`
		}
		if err := json.Unmarshal(body, &batch); err != nil {
			return nil, fmt.Errorf("decode messages: %w", err)
		}
		raw = append(raw, batch...)
		if len(batch) < batchSize {
			break
		}
		offset += batchSize
	}
	waiting, err := waitingSends(ctx, ownerID)
	if err != nil {
		return nil, err
	}
	var candidates []reprocessRow
	for _, r := range raw {
		row := r.reprocessRow
		row.HasBody, row.HasDraft = r.Body != nil && *r.Body != "", r.Draft != nil && *r.Draft != ""
		if reason := skipReason(row, waiting); reason != "" {
			totals["skipped: "+reason]++
			continue
		}
		candidates = append(candidates, row)
	}
	return candidates, nil
}

func isClaimActive(claimedUntil *string) bool {
	if claimedUntil == nil || *claimedUntil == "" {
		return false
	}
	t, err := time.Parse(time.RFC3339, *claimedUntil)
	if err != nil {
		t, err = time.Parse("2006-01-02T15:04:05.999999-07:00", *claimedUntil)
	}
	if err != nil {
		return false
	}
	return time.Now().UTC().Before(t.UTC())
}

func skipReason(row reprocessRow, waiting map[string]bool) string {
	switch {
	case row.SentAt != nil:
		return skipReplied
	case row.MaskingStatus != maskingComplete:
		return skipNotComplete
	case !row.HasBody:
		return skipPastRetention
	case waiting[row.ID]:
		return skipSendWaiting
	case isClaimActive(row.GenerationClaimedUntil):
		return skipClaimActive
	}
	return ""
}

// waitingSends are emails with a reply held for later: clearing their draft would break the send.
func waitingSends(ctx context.Context, ownerID string) (map[string]bool, error) {
	body, err := supabaseGet(ctx, "scheduled_send",
		"select=message_id&sent_at=is.null&cancelled_reason=is.null&"+ownerFilter(ownerID))
	if err != nil {
		return nil, err
	}
	var rows []struct {
		MessageID string `json:"message_id"`
	}
	if err := json.Unmarshal(body, &rows); err != nil {
		return nil, fmt.Errorf("decode scheduled sends: %w", err)
	}
	waiting := make(map[string]bool, len(rows))
	for _, row := range rows {
		waiting[row.MessageID] = true
	}
	return waiting, nil
}

func reprocessOne(ctx context.Context, ownerID string, row reprocessRow, srv *gmail.Service) string {
	ref := messageRef{ownerID: ownerID, msgID: row.GmailMessageID}
	msg, err := fetchMessage(ctx, srv, ref)
	switch {
	case isGone(err):
		return "skipped: " + skipGone
	case err != nil || msg.Payload == nil:
		return "skipped: " + skipFetchFailed
	}
	content, isComplete := maskMessage(ctx, srv, msg, ownerID)
	if !isComplete {
		// Never stored half-masked: the old, fully masked copy stays.
		return "skipped: " + skipNotMasked
	}
	patch := reprocessPatch{
		MaskedContent:  content,
		ActionItems:    []string{},
		SlaPriority:    ClassifySLA(content.Subject, content.BodyMasked, time.Now().UTC()),
		CriticAttempts: 0,
	}
	if err := supabasePatch(ctx, "messages", "id=eq."+url.QueryEscape(row.ID), patch); err != nil {
		log.Printf("email %s not stored: %v", row.ID, err)
		return "failed to store"
	}
	ref.audit(ctx, actionRemaskMessage, auditFields{fieldReason: reasonReprocessed}, true)
	time.Sleep(reprocessPause)
	return "changed"
}

func printTotals(job string, totals map[string]int, isWrite bool) {
	mode := "dry run: nothing was written"
	if isWrite {
		mode = "written"
	}
	fmt.Printf("%s (%s)\n", job, mode)
	for reason, count := range totals {
		fmt.Printf("  %-45s %d\n", reason, count)
	}
}
