package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
	"testing"

	"google.golang.org/api/googleapi"
)

func TestADetailIsCompactJSONWithSortedKeys(t *testing.T) {
	got := encodeDetail(auditFields{fieldReason: "a<b&c", fieldGmailMessageID: "18f", fieldPages: 2})
	want := `{"gmail_message_id":"18f","pages":2,"reason":"a<b&c"}`
	if got != want {
		t.Fatalf("want %s, got %s", want, got)
	}
	if encodeDetail(nil) != "{}" {
		t.Fatal("a row without fields still holds a JSON object")
	}
}

func TestAnErrorKindNeverCarriesItsText(t *testing.T) {
	leaky := fmt.Errorf("wrapped: %w", &googleapi.Error{Code: 404, Message: "no mail for aisyah@corp.example"})
	if got := errorKind(leaky); got != "gmail_http_404" {
		t.Fatalf("got %q", got)
	}
	if got := errorKind(errors.New("Dear Aisyah, your IC 880101-14-5523")); got != errKindOther {
		t.Fatalf("got %q", got)
	}
	if got := errorKind(fmt.Errorf("%w: status 400", errRowRejected)); got != errKindRowRejected {
		t.Fatalf("got %q", got)
	}
}

func recordAuditRows(t *testing.T) *[]AuditLogEntry {
	t.Helper()
	var rows []AuditLogEntry
	withSupabase(t, func(w http.ResponseWriter, r *http.Request) {
		if !strings.HasSuffix(r.URL.Path, "/audit_log") {
			return
		}
		raw, _ := io.ReadAll(r.Body)
		var entry AuditLogEntry
		if err := json.Unmarshal(raw, &entry); err != nil {
			t.Errorf("audit row is not JSON: %s", raw)
		}
		rows = append(rows, entry)
	})
	return &rows
}

func TestAnAuditRowNamesItsOwnerAndMessage(t *testing.T) {
	rows := recordAuditRows(t)
	messageRef{ownerID: "user-a", msgID: "m1"}.audit(context.Background(), actionStoreMessage,
		auditFields{fieldEmailsMasked: 1}, true)
	if len(*rows) != 1 || (*rows)[0].UserID != "user-a" || (*rows)[0].Action != actionStoreMessage {
		t.Fatalf("got %+v", *rows)
	}
	if (*rows)[0].Detail != `{"emails_masked":1,"gmail_message_id":"m1"}` {
		t.Fatalf("got detail %s", (*rows)[0].Detail)
	}
}

func TestAnUnownedAuditRowOmitsUserID(t *testing.T) {
	encoded, _ := json.Marshal(AuditLogEntry{Action: actionSetupWatch, Detail: "{}"})
	if strings.Contains(string(encoded), "user_id") {
		t.Fatalf("the token.json mailbox has no owner to name: %s", encoded)
	}
}
