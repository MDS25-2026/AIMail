package main

import (
	"encoding/base64"
	"mime"
	"strings"
	"unicode/utf8"

	"golang.org/x/text/encoding/htmlindex"
	"google.golang.org/api/gmail/v1"
)

// collectParts joins every body part of this MIME type in reading order, skipping attachments. A
// message can carry several (a forwarded email, a mailer that splits the body); keeping only the first
// dropped the rest, and with it any detail that needed masking or answering.
func collectParts(part *gmail.MessagePart, mimeType string) string {
	var bodies []string
	var walk func(p *gmail.MessagePart)
	walk = func(p *gmail.MessagePart) {
		if p.MimeType == mimeType && p.Filename == "" {
			if body := decodePart(p); body != "" {
				bodies = append(bodies, body)
			}
		}
		for _, sub := range p.Parts {
			walk(sub)
		}
	}
	walk(part)
	return strings.Join(bodies, "\n\n")
}

// decodePart returns the part's body as UTF-8. Gmail sends it base64url-encoded, sometimes without
// padding, in whatever charset the sender used: Chinese mail is often GB2312, GBK or Big5, which read as
// UTF-8 turns into garbage the masker cannot match names in.
func decodePart(part *gmail.MessagePart) string {
	if part.Body == nil || part.Body.Data == "" {
		return ""
	}
	data, err := base64.URLEncoding.DecodeString(part.Body.Data)
	if err != nil {
		if data, err = base64.RawURLEncoding.DecodeString(part.Body.Data); err != nil {
			return ""
		}
	}
	return toUTF8(data, charsetOf(part))
}

func charsetOf(part *gmail.MessagePart) string {
	for _, header := range part.Headers {
		if strings.EqualFold(header.Name, "Content-Type") {
			if _, params, err := mime.ParseMediaType(header.Value); err == nil {
				return params["charset"]
			}
		}
	}
	return ""
}

// toUTF8 converts from the declared charset; an unknown or wrong one still yields valid UTF-8 (bad
// bytes replaced) rather than a string Postgres or the masker would choke on.
func toUTF8(data []byte, charset string) string {
	if charset != "" && !strings.EqualFold(charset, "utf-8") && !strings.EqualFold(charset, "us-ascii") {
		if encoding, err := htmlindex.Get(charset); err == nil {
			if decoded, err := encoding.NewDecoder().Bytes(data); err == nil {
				return string(decoded)
			}
		}
	}
	if utf8.Valid(data) {
		return string(data)
	}
	return strings.ToValidUTF8(string(data), "\uFFFD")
}
