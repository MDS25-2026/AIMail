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
