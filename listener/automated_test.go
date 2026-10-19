package main

import (
	"testing"

	"google.golang.org/api/gmail/v1"
)

func headers(pairs ...string) []*gmail.MessagePartHeader {
	var out []*gmail.MessagePartHeader
	for i := 0; i+1 < len(pairs); i += 2 {
		out = append(out, &gmail.MessagePartHeader{Name: pairs[i], Value: pairs[i+1]})
	}
	return out
}

// A holding reply to any of these would answer a robot, or start a loop with another responder.
func TestAutomatedMailIsRecognised(t *testing.T) {
	cases := map[string][]*gmail.MessagePartHeader{
		"mailing list":       headers("From", "Team <team@corp.com>", "List-Id", "<news.corp.com>"),
		"newsletter":         headers("From", "Shop <hello@shop.com>", "List-Unsubscribe", "<mailto:u@shop.com>"),
		"bulk":               headers("From", "a@b.com", "Precedence", "Bulk"),
		"another auto-reply": headers("From", "a@b.com", "Auto-Submitted", "auto-replied"),
		"bounce":             headers("From", "a@b.com", "Return-Path", "<>"),
		"noreply sender":     headers("From", "Agoda <no-reply@agoda.com>"),
		"no_reply sender":    headers("From", "Support <no_reply@service.com>"),
		"do_not_reply":       headers("From", "Alerts <do_not_reply@bank.com>"),
		"mailer daemon":      headers("From", "MAILER-DAEMON@mail.example.com"),
	}
	for name, h := range cases {
		if !isAutomated(h, nil) {
			t.Errorf("%s was not recognised as automated", name)
		}
	}
}

func TestAPersonsEmailIsNotAutomated(t *testing.T) {
	for _, h := range [][]*gmail.MessagePartHeader{
		headers("From", "Aisyah <aisyah@example.com>"),
		headers("From", "Reply Team <replyteam@corp.com>", "Auto-Submitted", "no"),
		headers("From", "Noreen <noreen@corp.com>"),
	} {
		if isAutomated(h, nil) {
			t.Errorf("a person's email was treated as automated: %v", h[0].Value)
		}
	}
}

func TestGmailsNonPrimaryTabsAreAutomated(t *testing.T) {
	person := headers("From", "Milanote <hello@milanote.com>")
	for _, label := range []string{"CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL", "CATEGORY_UPDATES", "CATEGORY_FORUMS"} {
		if !isAutomated(person, []string{"INBOX", label}) {
			t.Errorf("mail in %s was not treated as automated", label)
		}
	}
	if isAutomated(person, []string{"INBOX", "CATEGORY_PERSONAL", "IMPORTANT"}) {
		t.Error("mail in the Primary tab was treated as automated")
	}
}
