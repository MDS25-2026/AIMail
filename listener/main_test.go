package main

import (
	"context"
	"strings"
	"testing"
)

// The security property of the layered masker: when Presidio is unreachable, the regex floor
// still masks structured PII and raw text is never returned.
func TestMaskTextKeepsRegexFloorWhenPresidioDown(t *testing.T) {
	t.Setenv("PRESIDIO_ANALYZER_URL", "http://127.0.0.1:1/analyze") // closed port -> connection refused

	masked, emails, _, degraded := maskText(context.Background(), "reach me at john@example.com")

	if strings.Contains(masked, "john@example.com") {
		t.Fatalf("email leaked through the degraded path: %q", masked)
	}
	if emails != 1 {
		t.Fatalf("expected 1 email masked by the regex floor, got %d", emails)
	}
	if !degraded {
		t.Fatal("expected degraded=true when Presidio is unreachable")
	}
}

// The refinement: format-clear numbers are typed by structure, not misread by length. Each
// input must redact to its OWN token and never carry the raw digits through.
func TestMaskPIITypesNumbersByStructure(t *testing.T) {
	cases := []struct {
		name  string
		in    string
		token string
		raw   string
	}{
		{"dashed IC", "IC 880101-14-5523 on file", icToken, "880101-14-5523"},
		{"bare 12-digit IC (valid date)", "id 880101145523 here", icToken, "880101145523"},
		{"MY mobile", "call 012-345 6789 today", phoneToken, "012-345 6789"},
		{"MY mobile no separators", "call 0123456789 today", phoneToken, "0123456789"},
		{"US parenthesized", "call (713) 853-6161 now", phoneToken, "(713) 853-6161"},
		{"US dashed", "at 713-853-6161 ext", phoneToken, "713-853-6161"},
		{"email", "mail me at a.b@corp.com", emailToken, "a.b@corp.com"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			masked, _, _ := maskPII(c.in)
			if !strings.Contains(masked, c.token) {
				t.Fatalf("expected %s in %q", c.token, masked)
			}
			if strings.Contains(masked, c.raw) {
				t.Fatalf("raw value %q leaked: %q", c.raw, masked)
			}
		})
	}
}

// A 12-digit IC must not be mis-tagged as a phone (the exact failure JJ reported).
func TestMaskPIIDoesNotTagICAsPhone(t *testing.T) {
	masked, _, phones := maskPII("my ic is 880101-14-5523")
	if phones != 0 {
		t.Fatalf("IC counted as a phone (%d) — type discrimination broke: %q", phones, masked)
	}
	if !strings.Contains(masked, icToken) {
		t.Fatalf("IC not redacted: %q", masked)
	}
}

// A bare 12-digit number whose prefix is not a plausible date is NOT an IC — it's left for
// Presidio's context-gated account recogniser rather than being falsely typed here.
func TestMaskPIILeavesNonDateBare12Digits(t *testing.T) {
	masked, _, _ := maskPII("order 990099123456 shipped")
	if strings.Contains(masked, icToken) {
		t.Fatalf("non-date 12-digit run wrongly typed as IC: %q", masked)
	}
}

// isICDate is the sole gate between "IC" and "arbitrary 12 digits", so each calendar
// boundary gets pinned explicitly.
func TestIsICDateAcceptsOnlyPlausibleCalendarPrefixes(t *testing.T) {
	cases := []struct {
		name string
		in   string
		want bool
	}{
		{"january first", "880101145523", true},
		{"december thirty-first", "881231145523", true},
		{"month zero", "880001145523", false},
		{"month thirteen", "881301145523", false},
		{"day zero", "880100145523", false},
		{"day thirty-two", "880132145523", false},
		{"wrong length", "8801011455", false},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := isICDate(c.in); got != c.want {
				t.Fatalf("isICDate(%q) = %v, want %v", c.in, got, c.want)
			}
		})
	}
}

// A real email carries several PII types at once; each regex pass must still see the
// spans earlier passes left behind, and the audit counts must reflect every hit.
func TestMaskPIIMasksEveryOccurrenceInMixedText(t *testing.T) {
	in := "From ali@corp.com.my: IC 880101-14-5523, backup a.b+tag@Mail.Example.COM, call 012-345 6789 or (713) 853-6161."
	masked, emails, phones := maskPII(in)
	for _, raw := range []string{"ali@corp.com.my", "880101-14-5523", "a.b+tag@Mail.Example.COM", "012-345 6789", "(713) 853-6161"} {
		if strings.Contains(masked, raw) {
			t.Errorf("raw value %q leaked: %q", raw, masked)
		}
	}
	if emails != 2 {
		t.Errorf("expected 2 emails counted, got %d", emails)
	}
	if phones != 2 {
		t.Errorf("expected 2 phones counted, got %d", phones)
	}
}

// Country-code prefixes are the phone branch most likely to regress; the +60 forms are
// what Malaysian signatures actually contain.
func TestMaskPIIMasksMalaysianCountryCodeVariants(t *testing.T) {
	cases := []struct{ name, in, raw string }{
		{"plus sixty solid", "reach me on +60123456789 thanks", "+60123456789"},
		{"plus sixty separated", "reach me on +6012-345 6789 thanks", "+6012-345 6789"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			masked, _, phones := maskPII(c.in)
			if strings.Contains(masked, c.raw) {
				t.Fatalf("raw value %q leaked: %q", c.raw, masked)
			}
			if phones != 1 {
				t.Fatalf("expected 1 phone counted, got %d: %q", phones, masked)
			}
		})
	}
}

// Over-masking commercial numerals would corrupt drafts and RAG text, so plain business
// digits (POs, invoice codes, amounts, ISO dates) must pass through byte-identical.
func TestMaskPIILeavesBusinessNumbersUntouched(t *testing.T) {
	in := "PO 12345678, invoice INV-2026-0831, total 1,250.00 due 2026-09-15"
	masked, emails, phones := maskPII(in)
	if masked != in {
		t.Fatalf("business text altered:\n in: %q\nout: %q", in, masked)
	}
	if emails != 0 || phones != 0 {
		t.Fatalf("phantom counts on clean text: emails=%d phones=%d", emails, phones)
	}
}

// Storing raw HTML silently degraded NER: a name immediately after a tag scores below the
// confidence threshold and survives masking, while the same name in prose is caught. This pins
// the stripping that keeps the masker seeing sentences.
func TestHTMLToTextProducesProse(t *testing.T) {
	markup := `<div dir="ltr"><style>.x{color:red}</style><p dir="ltr">Hi,</p>` +
		`<p dir="ltr">That&#39;s the invoice.<br>Regards,</p></div>`
	got := htmlToText(markup)

	for _, unwanted := range []string{"<p", "<div", "&#39;", "color:red"} {
		if strings.Contains(got, unwanted) {
			t.Errorf("markup survived stripping (%q): %q", unwanted, got)
		}
	}
	if !strings.Contains(got, "That's the invoice.") {
		t.Errorf("entity not unescaped: %q", got)
	}
	if !strings.Contains(got, "Hi,\n") {
		t.Errorf("block tags should become line breaks so sentences don't run together: %q", got)
	}
}
