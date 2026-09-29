package main

import (
	"encoding/json"
	"strings"
	"testing"

	"google.golang.org/api/gmail/v1"
)

func TestThreadIdentityReadsHeadersCaseInsensitively(t *testing.T) {
	msg := &gmail.Message{
		ThreadId: "thread-1",
		Payload: &gmail.MessagePart{Headers: []*gmail.MessagePartHeader{
			{Name: "Message-Id", Value: "<abc@mail.example.com>"},
			{Name: "REFERENCES", Value: "<root@mail.example.com>"},
		}},
	}
	got := threadIdentity(msg)
	want := ThreadIdentity{
		ThreadID: "thread-1", RFC822MessageID: "<abc@mail.example.com>",
		ThreadRefs: "<root@mail.example.com>",
	}
	if got != want {
		t.Fatalf("got %+v, want %+v", got, want)
	}
}

func TestThreadIdentityOfAFirstMessageHasNoReferences(t *testing.T) {
	msg := &gmail.Message{ThreadId: "t", Payload: &gmail.MessagePart{}}
	if got := threadIdentity(msg); got.ThreadRefs != "" || got.RFC822MessageID != "" {
		t.Fatalf("want empty headers, got %+v", got)
	}
}

func TestStoredMessageSendsThreadColumnsFlatAndOmitsEmptyOnes(t *testing.T) {
	row := StoredMessage{ThreadIdentity: ThreadIdentity{ThreadID: "t-1"}}
	encoded, err := json.Marshal(row)
	if err != nil {
		t.Fatal(err)
	}
	text := string(encoded)
	if !strings.Contains(text, `"thread_id":"t-1"`) || strings.Contains(text, "thread_refs") {
		t.Fatalf("thread columns must be top-level and omitted when empty: %s", text)
	}
}
