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
