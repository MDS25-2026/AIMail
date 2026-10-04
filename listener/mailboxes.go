package main

// Every Gmail account the listener ingests (specs/features/per-user-mailboxes.md, step 4).
//
// Each user who signed in with Google has a mailbox_connection row holding their refresh token,
// sealed by the backend. The listener loads those rows, watches each mailbox on the shared Pub/Sub
// topic, and routes every notification by its emailAddress. The original token.json mailbox stays
// as the one with no owner until its account connects, at which point its connection replaces it.

import (
	"context"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/url"
	"os"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"golang.org/x/oauth2"
	"golang.org/x/oauth2/google"
	"google.golang.org/api/gmail/v1"
	"google.golang.org/api/option"
)

const (
	// How often new sign-ups are picked up without a restart.
	connectionSyncInterval = 2 * time.Minute
	// A newly connected inbox gets its latest few emails at once, not only mail that arrives later.
	seedMessageCount = 10
)

// mailbox is one Gmail account. ownerID "" is the original token.json mailbox, stored unowned.
type mailbox struct {
	ownerID       string
	email         string
	srv           *gmail.Service
	lastHistoryID uint64 // atomic: notifications for one mailbox are handled concurrently
}

var registry = struct {
	sync.RWMutex
	byEmail map[string]*mailbox
}{byEmail: map[string]*mailbox{}}

func lookupMailbox(email string) *mailbox {
	registry.RLock()
	defer registry.RUnlock()
	return registry.byEmail[strings.ToLower(email)]
}

func mailboxByOwner(ownerID string) *mailbox {
	registry.RLock()
	defer registry.RUnlock()
	for _, mb := range registry.byEmail {
		if mb.ownerID == ownerID {
			return mb
		}
	}
	return nil
}

func allMailboxes() []*mailbox {
	registry.RLock()
	defer registry.RUnlock()
	out := make([]*mailbox, 0, len(registry.byEmail))
	for _, mb := range registry.byEmail {
		out = append(out, mb)
	}
	return out
}

// registerMailbox adds or replaces the mailbox for its address; a connection replaces the
// token.json mailbox of the same address, so the two never ingest the same mail twice.
func registerMailbox(mb *mailbox) {
	registry.Lock()
	defer registry.Unlock()
	registry.byEmail[strings.ToLower(mb.email)] = mb
}

type connectionRow struct {
	UserID    string  `json:"user_id"`
	Email     string  `json:"email"`
	Sealed    string  `json:"refresh_token_encrypted"`
	HistoryID *uint64 `json:"history_id"`
}

var errNotHexBytea = errors.New(`bytea column is not in PostgREST's \x hex form`)

// decodeBytea reads a bytea column as PostgREST returns it in JSON: `\x` then hex.
func decodeBytea(text string) ([]byte, error) {
	if !strings.HasPrefix(text, `\x`) {
		return nil, errNotHexBytea
	}
	return hex.DecodeString(text[2:])
}

func loadConnections(ctx context.Context) ([]connectionRow, error) {
	body, err := supabaseGet(ctx, "mailbox_connection",
		"select=user_id,email,refresh_token_encrypted,history_id&provider=eq.gmail")
	if err != nil {
		return nil, err
	}
	var rows []connectionRow
	if err := json.Unmarshal(body, &rows); err != nil {
		return nil, fmt.Errorf("decode connections: %w", err)
	}
	return rows, nil
}

// connectionService is a Gmail client acting as the user. Their token was issued to the web client
// configured in Supabase, so it can only be refreshed with that client's id and secret.
func connectionService(ctx context.Context, row connectionRow) (*gmail.Service, error) {
	clientID, clientSecret := os.Getenv("GOOGLE_OAUTH_CLIENT_ID"), os.Getenv("GOOGLE_OAUTH_CLIENT_SECRET")
	if clientID == "" || clientSecret == "" {
		return nil, errors.New("GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET are required")
	}
	sealed, err := decodeBytea(row.Sealed)
	if err != nil {
		return nil, err
	}
	refreshToken, err := unsealToken(os.Getenv("TOKEN_ENCRYPTION_KEY"), sealed, row.UserID)
	if err != nil {
		return nil, err
	}
	config := &oauth2.Config{ClientID: clientID, ClientSecret: clientSecret, Endpoint: google.Endpoint,
		Scopes: []string{gmail.GmailReadonlyScope}}
	tokens := config.TokenSource(ctx, &oauth2.Token{RefreshToken: refreshToken})
	return gmail.NewService(ctx, option.WithTokenSource(tokens))
}

// syncConnections starts ingesting every connection not yet registered. A connection that cannot
// be used (revoked, unreadable, watch refused) is logged and retried next sync; it never stops the
// others.
func syncConnections(ctx context.Context) {
	rows, err := loadConnections(ctx)
	if err != nil {
		log.Printf("could not load mailbox connections: %v", err)
		return
	}
	for _, row := range rows {
		if existing := lookupMailbox(row.Email); existing != nil && existing.ownerID == row.UserID {
			continue
		}
		if err := startConnection(ctx, row); err != nil {
			log.Printf("mailbox for user %s not started, will retry: %v", row.UserID, err)
			writeAuditLog(ctx, "start_mailbox", fmt.Sprintf("user %s: %v", row.UserID, err), false)
		}
	}
}

func startConnection(ctx context.Context, row connectionRow) error {
	srv, err := connectionService(ctx, row)
	if err != nil {
		return err
	}
	mb := &mailbox{ownerID: row.UserID, email: strings.ToLower(row.Email), srv: srv}
	isFirstStart := row.HistoryID == nil
	if !isFirstStart {
		// Resume where the last run stopped, so mail that arrived while it was down is listed.
		mb.lastHistoryID = *row.HistoryID
	}
	if err := watchMailbox(ctx, mb); err != nil {
		return err
	}
	registerMailbox(mb)
	log.Printf("ingesting the mailbox of user %s", row.UserID)
	writeAuditLog(ctx, "start_mailbox", fmt.Sprintf("user %s connected", row.UserID), true)
	if isFirstStart {
		go seedInbox(ctx, mb)
	}
	return nil
}

// watchMailbox asks Gmail to notify the shared topic about this inbox. Gmail drops a watch after
// about seven days; renewWatchPeriodically calls this again daily.
func watchMailbox(ctx context.Context, mb *mailbox) error {
	res, err := mb.srv.Users.Watch("me", &gmail.WatchRequest{TopicName: TopicName, LabelIds: []string{"INBOX"}}).
		Context(ctx).Do()
	if err != nil {
		return fmt.Errorf("watch: %w", err)
	}
	atomic.CompareAndSwapUint64(&mb.lastHistoryID, 0, res.HistoryId)
	saveConnectionState(ctx, mb, map[string]interface{}{
		"history_id":       atomic.LoadUint64(&mb.lastHistoryID),
		"watch_expires_at": time.UnixMilli(res.Expiration).UTC(),
	})
	return nil
}

// seedInbox stores the newest few inbox emails of a mailbox seen for the first time.
func seedInbox(ctx context.Context, mb *mailbox) {
	list, err := mb.srv.Users.Messages.List("me").LabelIds("INBOX").MaxResults(seedMessageCount).Context(ctx).Do()
	if err != nil {
		log.Printf("could not list the first emails for user %s: %v", mb.ownerID, err)
		return
	}
	for _, m := range list.Messages {
		if err := ingestMessage(ctx, mb, m.Id); err != nil {
			log.Printf("seeding user %s: %v", mb.ownerID, err)
		}
	}
}

// saveConnectionState persists a connection's baseline and watch expiry. Best effort: a failure
// only means the next restart lists a little more history than it needed to.
func saveConnectionState(ctx context.Context, mb *mailbox, fields map[string]interface{}) {
	if mb.ownerID == "" {
		return // token.json mailbox: its baseline lives in memory, as before
	}
	fields["updated_at"] = time.Now().UTC()
	if err := supabasePatch(ctx, "mailbox_connection", "user_id=eq."+url.QueryEscape(mb.ownerID), fields); err != nil {
		log.Printf("could not save the state of user %s's mailbox: %v", mb.ownerID, err)
	}
}

func syncConnectionsPeriodically(ctx context.Context) {
	ticker := time.NewTicker(connectionSyncInterval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			syncConnections(ctx)
		}
	}
}

// ownerFilter selects one mailbox's rows; the token.json mailbox's rows have no owner.
func ownerFilter(ownerID string) string {
	if ownerID == "" {
		return "user_id=is.null"
	}
	return "user_id=eq." + url.QueryEscape(ownerID)
}
