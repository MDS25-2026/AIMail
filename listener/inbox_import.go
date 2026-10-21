package main

// Importing past emails on a mailbox's first start (specs/features/inbox-import.md). Each email goes
// through ingestUnstored, so it is masked here before storage exactly like new mail, and quarantined
// with no content when NER is down (#109). The import runs outside the mailbox's ingesting lock:
// storing is idempotent (on_conflict=user_id,gmail_message_id), so a notification racing it is safe.

import (
	"context"
	"fmt"
	"log"
	"strconv"
	"sync"
	"sync/atomic"
	"time"
)

const (
	defaultImportLimit       = 20
	defaultImportDays        = 30
	defaultImportConcurrency = 3
	// Upper bounds on what the environment may ask for: this is a first look, not a mailbox copy.
	maxImportLimit       = 500
	maxImportDays        = 365
	maxImportConcurrency = 10
	// Gmail's largest page; a smaller cap asks for less.
	maxListPage     = 500
	importAttempts  = 4
	importBaseDelay = time.Second
)

// importSlots bounds the fetch-and-mask work of every import together, so several people connecting
// at once cannot flood Presidio or Gmail. New mail never waits on it: notifications do not use it.
var (
	importSlotsOnce sync.Once
	importSlots     chan struct{}
)

// importBackoff is how long to wait before retry attempt n (from 1); a variable so tests need not sleep.
var importBackoff = func(attempt int) time.Duration {
	return importBaseDelay << (attempt - 1)
}

type importSettings struct {
	limit       int
	days        int
	concurrency int
}

func importSettingsFromEnv() importSettings {
	return importSettings{
		limit:       boundedEnvInt("IMPORT_MESSAGE_LIMIT", defaultImportLimit, maxImportLimit),
		days:        boundedEnvInt("IMPORT_DAYS", defaultImportDays, maxImportDays),
		concurrency: boundedEnvInt("IMPORT_CONCURRENCY", defaultImportConcurrency, maxImportConcurrency),
	}
}

// boundedEnvInt is the variable as a number from 1 to most; anything else falls back to the default.
func boundedEnvInt(key string, fallback, most int) int {
	value, err := strconv.Atoi(getEnvOrDefault(key, strconv.Itoa(fallback)))
	if err != nil || value < 1 {
		return fallback
	}
	return min(value, most)
}

func importSemaphore(size int) chan struct{} {
	importSlotsOnce.Do(func() { importSlots = make(chan struct{}, size) })
	return importSlots
}

// inboxPage is one page of message ids and the token for the next ("" on the last page).
type inboxPage struct {
	ids  []string
	next string
}

type inboxLister func(ctx context.Context, query, pageToken string, pageSize int64) (inboxPage, error)

func gmailInboxLister(mb *mailbox) inboxLister {
	return func(ctx context.Context, query, pageToken string, pageSize int64) (inboxPage, error) {
		call := mb.srv.Users.Messages.List("me").Q(query).MaxResults(pageSize).Context(ctx)
		if pageToken != "" {
			call = call.PageToken(pageToken)
		}
		res, err := call.Do()
		if err != nil {
			return inboxPage{}, err
		}
		page := inboxPage{next: res.NextPageToken}
		for _, m := range res.Messages {
			page.ids = append(page.ids, m.Id)
		}
		return page, nil
	}
}

// importInbox stores the newest inbox emails of a mailbox seen for the first time, up to the limit.
func importInbox(ctx context.Context, mb *mailbox) {
	settings := importSettingsFromEnv()
	ids, err := recentInboxIDs(ctx, gmailInboxLister(mb), settings)
	if err != nil {
		log.Printf("could not list the first emails for user %s: %v", mb.ownerID, err)
		writeAuditLog(ctx, mb.ownerID, actionImportInbox, auditFields{fieldErrorKind: errorKind(err)}, false)
		return
	}
	fresh, ingest := newMessages(ctx, mb, ids)
	imported, failed := ingestAll(ctx, mb, fresh, ingest, importSemaphore(settings.concurrency))
	log.Printf("imported %d of %d recent emails for user %s (%d failed)", imported, len(fresh), mb.ownerID, failed)
	writeAuditLog(ctx, mb.ownerID, actionImportInbox, auditFields{fieldListed: len(ids), fieldImported: imported,
		fieldFailed: failed}, failed == 0)
}

// recentInboxIDs lists the newest inbox emails from the last settings.days, across pages, up to the limit.
func recentInboxIDs(ctx context.Context, list inboxLister, settings importSettings) ([]string, error) {
	query := fmt.Sprintf("in:inbox newer_than:%dd", settings.days)
	var ids []string
	token := ""
	for len(ids) < settings.limit {
		pageSize := int64(min(settings.limit-len(ids), maxListPage))
		page, err := withGmailRetry(ctx, func() (inboxPage, error) { return list(ctx, query, token, pageSize) })
		if err != nil {
			return nil, err
		}
		ids = append(ids, page.ids...)
		if page.next == "" || len(page.ids) == 0 {
			break
		}
		token = page.next
	}
	return ids[:min(len(ids), settings.limit)], nil
}

// ingestAll ingests ids with at most cap(slots) running at once across every import, newest first.
func ingestAll(ctx context.Context, mb *mailbox, ids []string, ingest ingestFunc, slots chan struct{}) (int, int) {
	var imported, failed atomic.Int64
	var wg sync.WaitGroup
	for _, msgID := range ids {
		select {
		case slots <- struct{}{}:
		case <-ctx.Done():
			wg.Wait()
			return int(imported.Load()), int(failed.Load())
		}
		wg.Add(1)
		go func() {
			defer func() { <-slots; wg.Done() }()
			_, err := withGmailRetry(ctx, func() (struct{}, error) { return struct{}{}, ingest(ctx, mb, msgID) })
			if err != nil {
				log.Printf("importing for user %s: %v", mb.ownerID, err)
				failed.Add(1)
				return
			}
			imported.Add(1)
		}()
	}
	wg.Wait()
	return int(imported.Load()), int(failed.Load())
}

// withGmailRetry retries a call that hit a rate limit, a 5xx or no answer, waiting longer each time.
// Anything else (a refused token, a message gone) fails at once: retrying cannot change it.
func withGmailRetry[T any](ctx context.Context, call func() (T, error)) (T, error) {
	var result T
	var err error
	for attempt := 1; attempt <= importAttempts; attempt++ {
		result, err = call()
		if err == nil || !isGmailTrouble(err) || attempt == importAttempts {
			return result, err
		}
		select {
		case <-time.After(importBackoff(attempt)):
		case <-ctx.Done():
			return result, ctx.Err()
		}
	}
	return result, err
}
