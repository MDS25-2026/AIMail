package main

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"google.golang.org/api/gmail/v1"
	"google.golang.org/api/googleapi"
	"google.golang.org/api/option"
)

func noImportBackoff(t *testing.T) {
	t.Helper()
	previous := importBackoff
	importBackoff = func(int) time.Duration { return 0 }
	t.Cleanup(func() { importBackoff = previous })
}

// pagedLister serves ids in pages of pageSize, recording the size each call asked for.
func pagedLister(ids []string, pageSize int, asked *[]int64) inboxLister {
	return func(_ context.Context, query, token string, size int64) (inboxPage, error) {
		*asked = append(*asked, size)
		start := 0
		if token != "" {
			fmt.Sscanf(token, "%d", &start)
		}
		end := min(start+min(pageSize, int(size)), len(ids))
		page := inboxPage{ids: ids[start:end]}
		if end < len(ids) {
			page.next = fmt.Sprint(end)
		}
		return page, nil
	}
}

func idsFrom(n int) []string {
	ids := make([]string, n)
	for i := range ids {
		ids[i] = fmt.Sprintf("m%02d", i)
	}
	return ids
}

func TestTheImportPagesThroughTheInboxAndStopsAtTheLimit(t *testing.T) {
	var asked []int64
	ids, err := recentInboxIDs(context.Background(), pagedLister(idsFrom(20), 3, &asked),
		importSettings{limit: 7, days: 30, concurrency: 1})
	if err != nil || len(ids) != 7 || ids[0] != "m00" || ids[6] != "m06" {
		t.Fatalf("want the newest 7 ids, got %v (%v)", ids, err)
	}
	if fmt.Sprint(asked) != "[7 4 1]" {
		t.Fatalf("each page must ask only for what is still needed, asked %v", asked)
	}
}

func TestASmallInboxIsImportedWhole(t *testing.T) {
	var asked []int64
	ids, err := recentInboxIDs(context.Background(), pagedLister(idsFrom(4), 3, &asked),
		importSettings{limit: 50, days: 30, concurrency: 1})
	if err != nil || len(ids) != 4 || len(asked) != 2 {
		t.Fatalf("want all 4 ids over 2 pages, got %v over %d pages (%v)", ids, len(asked), err)
	}
}

func TestTheImportAsksOnlyForRecentInboxMail(t *testing.T) {
	var query string
	list := func(_ context.Context, q, _ string, _ int64) (inboxPage, error) { query = q; return inboxPage{}, nil }
	if _, err := recentInboxIDs(context.Background(), list, importSettings{limit: 50, days: 30}); err != nil {
		t.Fatal(err)
	}
	if query != "in:inbox newer_than:30d" {
		t.Fatalf("query = %q", query)
	}
}

func TestARateLimitIsWaitedOutAndAPermanentRefusalIsNot(t *testing.T) {
	noImportBackoff(t)
	calls := 0
	flaky := func(context.Context, string, string, int64) (inboxPage, error) {
		calls++
		if calls < 3 {
			return inboxPage{}, &googleapi.Error{Code: http.StatusTooManyRequests}
		}
		return inboxPage{ids: []string{"m1"}}, nil
	}
	ids, err := recentInboxIDs(context.Background(), flaky, importSettings{limit: 5, days: 30})
	if err != nil || len(ids) != 1 || calls != 3 {
		t.Fatalf("want success on the third try, got %v after %d calls (%v)", ids, calls, err)
	}

	calls = 0
	limited := func(context.Context, string, string, int64) (inboxPage, error) {
		calls++
		return inboxPage{}, &googleapi.Error{Code: http.StatusTooManyRequests}
	}
	if _, err := recentInboxIDs(context.Background(), limited, importSettings{limit: 5, days: 30}); err == nil ||
		calls != importAttempts {
		t.Fatalf("a rate limit that never lifts must give up after %d tries, got %d (%v)", importAttempts, calls, err)
	}

	calls = 0
	gone := func(context.Context, string, string, int64) (inboxPage, error) {
		calls++
		return inboxPage{}, &googleapi.Error{Code: http.StatusNotFound}
	}
	if _, err := recentInboxIDs(context.Background(), gone, importSettings{limit: 5, days: 30}); err == nil || calls != 1 {
		t.Fatalf("a refusal retrying cannot change is not retried, got %d calls (%v)", calls, err)
	}
}

func TestNoMoreThanTheSlotsIngestAtOnce(t *testing.T) {
	var running, most atomic.Int64
	slow := func(context.Context, *mailbox, string) error {
		now := running.Add(1)
		for {
			seen := most.Load()
			if now <= seen || most.CompareAndSwap(seen, now) {
				break
			}
		}
		time.Sleep(10 * time.Millisecond)
		running.Add(-1)
		return nil
	}
	imported, failed := ingestAll(context.Background(), &mailbox{}, idsFrom(12), slow, make(chan struct{}, 2))
	if imported != 12 || failed != 0 || most.Load() > 2 {
		t.Fatalf("want 12 imported with at most 2 at once, got %d/%d with %d at once", imported, failed, most.Load())
	}
}

func TestImportSettingsComeFromTheEnvironmentWithinBounds(t *testing.T) {
	t.Setenv("IMPORT_MESSAGE_LIMIT", "100000")
	t.Setenv("IMPORT_DAYS", "0")
	t.Setenv("IMPORT_CONCURRENCY", "not a number")
	got := importSettingsFromEnv()
	if got.limit != maxImportLimit || got.days != defaultImportDays || got.concurrency != defaultImportConcurrency {
		t.Fatalf("got %+v", got)
	}
}

// importWorld is a fake Gmail inbox, Supabase and (optionally) Presidio for a whole import.
type importWorld struct {
	mu       sync.Mutex
	inserted []string // request bodies posted to messages
	audits   []string // request bodies posted to audit_log
}

func newImportWorld(t *testing.T, inbox []string, alreadyStored []string, isNERUp bool) (*importWorld, *mailbox) {
	t.Helper()
	world := &importWorld{}
	stored := `[]`
	if len(alreadyStored) > 0 {
		rows := make([]string, len(alreadyStored))
		for i, id := range alreadyStored {
			rows[i] = fmt.Sprintf(`{"gmail_message_id":%q}`, id)
		}
		stored = "[" + strings.Join(rows, ",") + "]"
	}
	withSupabase(t, func(w http.ResponseWriter, r *http.Request) {
		raw, _ := io.ReadAll(r.Body)
		world.mu.Lock()
		defer world.mu.Unlock()
		switch {
		case r.Method == http.MethodGet && strings.HasSuffix(r.URL.Path, "/messages"):
			w.Write([]byte(stored))
		case r.Method == http.MethodPost && strings.HasSuffix(r.URL.Path, "/messages"):
			world.inserted = append(world.inserted, string(raw))
			w.Write([]byte(`[{"id":"row"}]`))
		case r.Method == http.MethodPost && strings.HasSuffix(r.URL.Path, "/audit_log"):
			world.audits = append(world.audits, string(raw))
		default:
			w.Write([]byte(`[]`))
		}
	})
	if isNERUp {
		fakePresidio(t)
	} else {
		t.Setenv("PRESIDIO_ANALYZER_URL", "http://127.0.0.1:1/analyze")
	}
	gmailServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		id := strings.TrimPrefix(r.URL.Path, "/gmail/v1/users/me/messages")
		if id == "" || id == "/" {
			list := gmail.ListMessagesResponse{}
			for _, msgID := range inbox {
				list.Messages = append(list.Messages, &gmail.Message{Id: msgID})
			}
			json.NewEncoder(w).Encode(list)
			return
		}
		msgID := strings.TrimPrefix(id, "/")
		json.NewEncoder(w).Encode(gmail.Message{Id: msgID, LabelIds: []string{"INBOX"}, Payload: &gmail.MessagePart{
			MimeType: "text/plain",
			Headers:  []*gmail.MessagePartHeader{{Name: "Subject", Value: "Invoice " + msgID}},
			Body:     &gmail.MessagePartBody{Data: base64.URLEncoding.EncodeToString([]byte("Please pay invoice " + msgID))},
		}})
	}))
	t.Cleanup(gmailServer.Close)
	srv, err := gmail.NewService(context.Background(), option.WithEndpoint(gmailServer.URL+"/"),
		option.WithoutAuthentication(), option.WithHTTPClient(gmailServer.Client()))
	if err != nil {
		t.Fatal(err)
	}
	return world, &mailbox{ownerID: "user-1", srv: srv}
}

func TestAFirstStartImportsTheInboxSkippingWhatIsStored(t *testing.T) {
	noImportBackoff(t)
	world, mb := newImportWorld(t, []string{"a1", "a2", "a3"}, []string{"a2"}, true)
	importInbox(context.Background(), mb)
	if len(world.inserted) != 2 {
		t.Fatalf("want the 2 unstored emails stored, got %d inserts", len(world.inserted))
	}
	for _, body := range world.inserted {
		if strings.Contains(body, `"a2"`) || !strings.Contains(body, `"masking_status":"complete"`) {
			t.Fatalf("unexpected insert: %s", body)
		}
	}
	last := world.audits[len(world.audits)-1]
	if !strings.Contains(last, `\"imported\":2`) {
		t.Fatalf("the import's audit row must count what it stored: %s", last)
	}
}

func TestWithNERDownImportedMailIsQuarantinedWithNoContent(t *testing.T) {
	noImportBackoff(t)
	world, mb := newImportWorld(t, []string{"b1"}, nil, false)
	importInbox(context.Background(), mb)
	if len(world.inserted) != 1 {
		t.Fatalf("want one quarantined row, got %d", len(world.inserted))
	}
	row := world.inserted[0]
	if !strings.Contains(row, `"masking_status":"pending"`) || strings.Contains(row, "Please pay invoice") ||
		strings.Contains(row, "Invoice b1") {
		t.Fatalf("a quarantined row keeps no content: %s", row)
	}
}

func TestAnImportThatCannotListLeavesAFailedAuditRow(t *testing.T) {
	noImportBackoff(t)
	world := &importWorld{}
	withSupabase(t, func(w http.ResponseWriter, r *http.Request) {
		if strings.HasSuffix(r.URL.Path, "/audit_log") {
			raw, _ := io.ReadAll(r.Body)
			world.audits = append(world.audits, string(raw))
		}
	})
	srv := fakeGmail(t, http.StatusForbidden, `{"error":{"code":403,"message":"no"}}`)
	importInbox(context.Background(), &mailbox{ownerID: "user-1", srv: srv})
	if len(world.audits) != 1 || !strings.Contains(world.audits[0], "import_inbox") ||
		!strings.Contains(world.audits[0], `"success":false`) {
		t.Fatalf("want one failed import_inbox row, got %v", world.audits)
	}
}
