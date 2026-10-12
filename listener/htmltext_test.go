package main

import (
	"encoding/base64"
	"strings"
	"testing"

	"google.golang.org/api/gmail/v1"
)

// The shape Outlook sends: MsoNormal paragraphs, &nbsp; spacers, a conditional comment, <o:p>.
const outlookHTML = `<html xmlns:o="urn:schemas-microsoft-com:office:office"><head>
<!--[if gte mso 9]><xml><o:OfficeDocumentSettings><o:AllowPNG/></o:OfficeDocumentSettings></xml><![endif]-->
<style>p.MsoNormal{margin:0cm;}</style></head><body lang=EN-US>
<div class=WordSection1>
<p class=MsoNormal>Hi Aisyah,<o:p></o:p></p>
<p class=MsoNormal><o:p>&nbsp;</o:p></p>
<p class=MsoNormal>Please find the quotation    below.<o:p></o:p></p>
<p class=MsoNormal><o:p>&nbsp;</o:p></p>
<p class=MsoNormal>Regards,<br>
Daniel<o:p></o:p></p>
</div></body></html>`

func TestOutlookSpacersCommentsAndOfficeTagsLeaveCleanParagraphs(t *testing.T) {
	got := htmlToText(outlookHTML)
	want := "Hi Aisyah,\n\nPlease find the quotation below.\n\nRegards,\nDaniel"
	if got != want {
		t.Fatalf("got %q\nwant %q", got, want)
	}
}

func TestListsKeepTheirBulletsAndNumbers(t *testing.T) {
	got := htmlToText(`<p>Steps:</p><ol><li>Sign</li><li>Return</li></ol><ul><li>One</li><li>Two</li></ul>`)
	for _, line := range []string{"1. Sign", "2. Return", "- One", "- Two"} {
		if !strings.Contains(got, "\n"+line) {
			t.Errorf("missing %q on its own line: %q", line, got)
		}
	}
}

func TestADataTableReadsAsRowsAndALayoutTableDoesNot(t *testing.T) {
	invoice := htmlToText(`<table><tr><th>Item</th><th>Amount</th></tr><tr><td>Paper</td><td>RM 120</td></tr></table>`)
	if !strings.Contains(invoice, "Item | Amount\nPaper | RM 120") {
		t.Errorf("data table: %q", invoice)
	}
	layout := htmlToText(`<table><tr><td><table><tr><td>Big sale this week on every chair and table we sell</td></tr></table></td>` +
		`<td>Unsubscribe</td></tr></table>`)
	if strings.Contains(layout, "|") {
		t.Errorf("layout table got pipes: %q", layout)
	}
}

func TestALinkWhoseTextIsItsAddressIsWrittenOnce(t *testing.T) {
	if got := htmlToText(`<a href="https://aimail.example/">https://aimail.example</a>`); got != "https://aimail.example" {
		t.Fatalf("got %q", got)
	}
}

func TestQuotedMailIsMarkedSoTheDashboardCanFoldIt(t *testing.T) {
	got := htmlToText(`<div>Sounds good.</div><blockquote><div>Can we meet</div><div>on Friday?</div></blockquote>`)
	if got != "Sounds good.\n\n> Can we meet\n> on Friday?" {
		t.Fatalf("got %q", got)
	}
}

func TestPreformattedTextKeepsItsSpacing(t *testing.T) {
	if got := htmlToText("<pre>Qty   Item\n2     Pens</pre>"); got != "Qty   Item\n2     Pens" {
		t.Fatalf("got %q", got)
	}
}

func bodyPart(mimeType, body string, headers ...*gmail.MessagePartHeader) *gmail.MessagePart {
	return &gmail.MessagePart{MimeType: mimeType, Headers: headers,
		Body: &gmail.MessagePartBody{Data: base64.URLEncoding.EncodeToString([]byte(body))}}
}

func TestGmailsHTMLPartIsPreferredOverItsHardWrappedText(t *testing.T) {
	plain := "Hi, could you confirm the delivery date for the order we placed last\nweek? Thanks."
	markup := `<div dir="ltr">Hi, could you confirm the delivery date for the order we placed last week? Thanks.</div>`
	message := &gmail.MessagePart{MimeType: "multipart/alternative",
		Parts: []*gmail.MessagePart{bodyPart("text/plain", plain), bodyPart("text/html", markup)}}
	if got := getBody(message); strings.Contains(got, "\n") {
		t.Fatalf("hard wrap survived: %q", got)
	}
}

func TestFlowedPlainTextJoinsItsSoftBreaks(t *testing.T) {
	flowed := bodyPart("text/plain", "This line goes \non here.\n-- \nDaniel",
		&gmail.MessagePartHeader{Name: "Content-Type", Value: `text/plain; charset="utf-8"; format=flowed`})
	if got := getBody(flowed); got != "This line goes on here.\n-- \nDaniel" {
		t.Fatalf("got %q", got)
	}
}
