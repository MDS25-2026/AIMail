package main

import (
	"encoding/base64"
	"testing"
	"unicode/utf8"

	"golang.org/x/text/encoding"
	"golang.org/x/text/encoding/charmap"
	"golang.org/x/text/encoding/simplifiedchinese"
	"golang.org/x/text/encoding/traditionalchinese"
	"google.golang.org/api/gmail/v1"
)

func encodedPart(t *testing.T, enc encoding.Encoding, charset, text string) *gmail.MessagePart {
	t.Helper()
	raw := []byte(text)
	if enc != nil {
		var err error
		if raw, err = enc.NewEncoder().Bytes(raw); err != nil {
			t.Fatalf("encode %s: %v", charset, err)
		}
	}
	return &gmail.MessagePart{
		MimeType: "text/plain",
		Headers:  []*gmail.MessagePartHeader{{Name: "Content-Type", Value: "text/plain; charset=" + charset}},
		Body:     &gmail.MessagePartBody{Data: base64.URLEncoding.EncodeToString(raw)},
	}
}

func TestBodiesInTheSendersCharsetAreReadAsUTF8(t *testing.T) {
	cases := []struct {
		charset string
		enc     encoding.Encoding
		text    string
	}{
		{"gbk", simplifiedchinese.GBK, "请在周五前回复，谢谢。"},
		{"big5", traditionalchinese.Big5, "請在週五前回覆。"},
		{"iso-8859-1", charmap.ISO8859_1, "Café réservé"},
		{"utf-8", nil, "Terima kasih, jumpa Jumaat."},
	}
	for _, c := range cases {
		got := decodePart(encodedPart(t, c.enc, c.charset, c.text))
		if got != c.text {
			t.Errorf("%s: got %q, want %q", c.charset, got, c.text)
		}
	}
}

func TestUnpaddedBase64IsAccepted(t *testing.T) {
	part := &gmail.MessagePart{Body: &gmail.MessagePartBody{Data: base64.RawURLEncoding.EncodeToString([]byte("Hi there"))}}
	if got := decodePart(part); got != "Hi there" {
		t.Errorf("got %q", got)
	}
}

func TestBrokenBytesStillGiveValidUTF8(t *testing.T) {
	part := &gmail.MessagePart{Body: &gmail.MessagePartBody{Data: base64.URLEncoding.EncodeToString([]byte{'O', 'K', 0xff, 0xfe})}}
	if got := decodePart(part); !utf8.ValidString(got) {
		t.Errorf("not valid UTF-8: %q", got)
	}
}

func TestEveryTextPartIsKeptAndAttachmentsAreNot(t *testing.T) {
	text := func(s string) *gmail.MessagePart {
		return &gmail.MessagePart{MimeType: "text/plain", Body: &gmail.MessagePartBody{Data: base64.URLEncoding.EncodeToString([]byte(s))}}
	}
	attachment := text("attached notes")
	attachment.Filename = "notes.txt"
	message := &gmail.MessagePart{MimeType: "multipart/mixed", Parts: []*gmail.MessagePart{text("First part."), attachment, text("Second part.")}}
	if got := getBody(message); got != "First part.\n\nSecond part." {
		t.Errorf("got %q", got)
	}
}

func TestAttachmentTypesComeFromTheBytesNotTheLabel(t *testing.T) {
	pdf := []byte("%PDF-1.7\n...")
	png := []byte("\x89PNG\r\n\x1a\n\x00\x00\x00\x00")
	zip := []byte("PK\x03\x04\x14\x00\x00\x00")
	cases := []struct {
		name, declared, filename string
		raw                      []byte
		want                     string
		isReadable               bool
	}{
		{"a real PDF", pdfMime, "a.pdf", pdf, pdfMime, true},
		{"a PDF label on something else", pdfMime, "a.pdf", []byte("MZ\x90\x00"), "", false},
		{"an image labelled as the wrong image type", "image/jpeg", "a.jpg", png, "image/png", true},
		{"an iPhone photo Go cannot sniff", "image/heic", "IMG_1.HEIC", []byte("\x00\x00\x00\x18ftypheic"), "image/heic", true},
		{"a PDF labelled as an image", "image/png", "a.png", pdf, "", false},
		{"an unlabelled PDF", octetStreamMime, "scan", pdf, pdfMime, true},
		{"an unlabelled docx", octetStreamMime, "Contract.DOCX", zip, docxMime, true},
		{"an unlabelled zip that is not Office", octetStreamMime, "photos.zip", zip, "", false},
		{"a docx label on something else", docxMime, "a.docx", pdf, "", false},
	}
	for _, c := range cases {
		got, isReadable := effectiveType(c.declared, c.filename, c.raw)
		// The type matters only for a file that will be read.
		if isReadable != c.isReadable || (isReadable && got != c.want) {
			t.Errorf("%s: got (%q, %v), want (%q, %v)", c.name, got, isReadable, c.want, c.isReadable)
		}
	}
}

func TestAttachmentsOfTypesNeverReadAreCounted(t *testing.T) {
	attached := func(mime string) *gmail.MessagePart {
		return &gmail.MessagePart{MimeType: mime, Body: &gmail.MessagePartBody{AttachmentId: "x", Size: 10}}
	}
	message := &gmail.MessagePart{Parts: []*gmail.MessagePart{attached(pdfMime), attached("application/msword"), attached(octetStreamMime), attached("application/zip")}}
	if got := unsupportedAttachments(message); got != 2 {
		t.Errorf("got %d, want 2 (the .doc and the zip)", got)
	}
}
