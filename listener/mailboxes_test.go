package main

import (
	"context"
	"encoding/base64"
	"encoding/hex"
	"io"
	"net/http"
	"strings"
	"testing"
)

func withMailboxes(t *testing.T, mbs ...*mailbox) {
	t.Helper()
	registry.Lock()
	saved := registry.byEmail
	registry.byEmail = map[string]*mailbox{}
	registry.Unlock()
	for _, mb := range mbs {
		registerMailbox(mb)
	}
	t.Cleanup(func() {
		registry.Lock()
		registry.byEmail = saved
		registry.Unlock()
	})
}

// PostgREST returns bytea as `\x` plus hex; the sealed token must survive that round trip.
func TestASealedTokenReadBackFromPostgRESTStillDecrypts(t *testing.T) {
	v := loadTokenVector(t)
	sealed, _ := base64.StdEncoding.DecodeString(v.Sealed)
	decoded, err := decodeBytea(`\x` + hex.EncodeToString(sealed))
	if err != nil {
		t.Fatal(err)
	}
	if got, err := unsealToken(v.Key, decoded, v.UserID); err != nil || got != v.Plaintext {
		t.Fatalf("got %q, %v", got, err)
	}
}

func TestABase64ByteaIsRefusedRatherThanMisread(t *testing.T) {
	if _, err := decodeBytea("AQID"); err == nil {
		t.Fatal("a value without the \\x prefix was accepted")
	}
}

// Notifications carry the address in whatever case Gmail sends; routing must not depend on it.
func TestANotificationIsRoutedToItsMailboxIgnoringCase(t *testing.T) {
	alice := &mailbox{ownerID: "user-a", email: "alice@gmail.com"}
	withMailboxes(t, alice, &mailbox{ownerID: "user-b", email: "bob@gmail.com"})
	if lookupMailbox("Alice@Gmail.com") != alice {
		t.Fatal("notification not routed to its own mailbox")
	}
	if lookupMailbox("stranger@gmail.com") != nil {
		t.Fatal("an unknown address matched a mailbox")
	}
}

// Once the token.json account connects, its connection replaces it, so mail is never ingested twice.
func TestAConnectionReplacesTheTokenFileMailboxOfTheSameAddress(t *testing.T) {
	withMailboxes(t, &mailbox{email: "owner@gmail.com"})
	registerMailbox(&mailbox{ownerID: "user-o", email: "Owner@gmail.com"})
	if got := lookupMailbox("owner@gmail.com"); got == nil || got.ownerID != "user-o" {
		t.Fatalf("connection did not replace the token.json mailbox: %+v", got)
	}
	if len(allMailboxes()) != 1 {
		t.Fatal("the same address is being ingested twice")
	}
}

func TestEachMailboxKeepsItsOwnBaseline(t *testing.T) {
	a, b := &mailbox{ownerID: ""}, &mailbox{ownerID: ""}
	advanceBaseline(a, 500)
	if b.lastHistoryID != 0 || a.lastHistoryID != 500 {
		t.Fatal("one mailbox's history moved another's baseline")
	}
}

func TestAConnectedMailboxSavesItsBaselineForTheNextRestart(t *testing.T) {
	var patches []string
	queries := withSupabase(t, func(w http.ResponseWriter, r *http.Request) {
		raw, _ := io.ReadAll(r.Body)
		patches = append(patches, r.Method+" "+string(raw))
	})
	advanceBaseline(&mailbox{ownerID: "user-a"}, 777)
	if len(patches) != 1 || !strings.HasPrefix(patches[0], "PATCH") || !strings.Contains(patches[0], `"history_id":777`) {
		t.Fatalf("baseline not saved: %v", patches)
	}
	if (*queries)[0] != "user_id=eq.user-a" {
		t.Fatalf("saved to the wrong row: %s", (*queries)[0])
	}
}

func TestStoredRowsCarryTheirOwnerAndTokenFileRowsHaveNone(t *testing.T) {
	var bodies []string
	queries := withSupabase(t, func(w http.ResponseWriter, r *http.Request) {
		raw, _ := io.ReadAll(r.Body)
		bodies = append(bodies, string(raw))
		w.Write([]byte(`[{"gmail_message_id":"m1"}]`))
	})
	insertMessage(context.Background(), StoredMessage{UserID: "user-a", GmailMessageID: "m1"})
	insertMessage(context.Background(), StoredMessage{GmailMessageID: "m2"})
	if !strings.Contains(bodies[0], `"user_id":"user-a"`) || strings.Contains(bodies[1], "user_id") {
		t.Fatalf("owner not stored as expected: %v", bodies)
	}
	if !strings.Contains((*queries)[0], "on_conflict=user_id,gmail_message_id") {
		t.Fatalf("duplicates must be judged per mailbox: %s", (*queries)[0])
	}
}

func TestADuplicateCheckOnlyLooksInTheSameMailbox(t *testing.T) {
	queries := withSupabase(t, func(w http.ResponseWriter, _ *http.Request) { w.Write([]byte(`[]`)) })
	messageStored(context.Background(), "user-a", "m1")
	if !strings.Contains((*queries)[0], "user_id=eq.user-a&gmail_message_id=eq.m1") {
		t.Fatalf("lookup not scoped to the mailbox: %s", (*queries)[0])
	}
}

// A connection that cannot start is retried every sync; repeating the same error must not write
// an audit row each time.
func TestARepeatedStartFailureIsAuditedOnce(t *testing.T) {
	t.Setenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
	withMailboxes(t)
	t.Cleanup(func() { clearFailure("user-a") })
	var audits int
	withSupabase(t, func(w http.ResponseWriter, r *http.Request) {
		if strings.HasSuffix(r.URL.Path, "/audit_log") {
			audits++
			return
		}
		w.Write([]byte(`[{"user_id":"user-a","email":"a@gmail.com","refresh_token_encrypted":"\\x01"}]`))
	})
	syncConnections(context.Background())
	syncConnections(context.Background())
	if audits != 1 {
		t.Fatalf("want 1 audit row for a repeated failure, got %d", audits)
	}
}

func TestSigningInAgainRestartsTheMailboxWithTheNewToken(t *testing.T) {
	withMailboxes(t, &mailbox{ownerID: "user-a", email: "a@gmail.com", sealed: `\x01`})
	if !isRunning(connectionRow{UserID: "user-a", Email: "a@gmail.com", Sealed: `\x01`}) {
		t.Fatal("an unchanged connection was restarted")
	}
	if isRunning(connectionRow{UserID: "user-a", Email: "a@gmail.com", Sealed: `\x02`}) {
		t.Fatal("a new token kept the old, possibly revoked, one running")
	}
}

// Disconnecting Gmail or deleting an account removes the connection row; the next sync must stop
// ingesting that mailbox, and must never touch the token.json mailbox, which has no row.
func TestADisconnectedMailboxIsDroppedOnTheNextSync(t *testing.T) {
	withSupabase(t, func(w http.ResponseWriter, _ *http.Request) { w.Write([]byte(`[]`)) })
	withMailboxes(t, &mailbox{ownerID: "user-a", email: "a@gmail.com"}, &mailbox{email: "owner@gmail.com"})
	syncConnections(context.Background())
	if lookupMailbox("a@gmail.com") != nil {
		t.Fatal("a disconnected mailbox is still being ingested")
	}
	if lookupMailbox("owner@gmail.com") == nil {
		t.Fatal("the token.json mailbox was dropped")
	}
}
