package main

// Live integration tests for the Presidio NER layer. Each test exercises maskText against
// the real analyzer/anonymizer containers and skips itself when they are unreachable, so
// `go test` stays green offline while the NER claims remain verifiable locally
// (docker compose up -d from the repo root).

import (
	"context"
	"strings"
	"testing"
	"time"
)

func requireLivePresidio(t *testing.T) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	// Both containers: with only the analyzer up, masking degrades and every assertion would fail
	// for a reason that is the environment, not the code.
	if !presidioHealthy(ctx) {
		t.Skip("presidio analyzer or anonymizer unreachable — start them: docker compose up -d")
	}
}

func TestMaskTextLiveMasksNamesAndLocations(t *testing.T) {
	requireLivePresidio(t)

	masked, _, _, degraded := maskText(context.Background(), "Please ask Sarah Tan in Kuala Lumpur to reply to the vendor.")

	if degraded {
		t.Fatal("degraded=true with a live analyzer")
	}
	for _, raw := range []string{"Sarah Tan", "Kuala Lumpur"} {
		if strings.Contains(masked, raw) {
			t.Errorf("%q leaked past NER masking: %q", raw, masked)
		}
	}
}

// The ad-hoc recogniser's base score (0.4) sits below the 0.6 threshold; only the context
// boost from nearby banking words lifts a digit run over it. Both sides of that gate are
// the security property, so both get a live test.
func TestMaskTextLiveMasksAccountNumberWithContext(t *testing.T) {
	requireLivePresidio(t)

	masked, _, _, degraded := maskText(context.Background(), "Wire the deposit to my Maybank account 512837465920 by Friday.")

	if degraded {
		t.Fatal("degraded=true with a live analyzer")
	}
	if strings.Contains(masked, "512837465920") {
		t.Fatalf("context-flanked account number leaked: %q", masked)
	}
}

func TestMaskTextLiveLeavesContextFreeDigitRun(t *testing.T) {
	requireLivePresidio(t)

	masked, _, _, _ := maskText(context.Background(), "We shipped 93842716 widgets on Friday.")

	if !strings.Contains(masked, "93842716") {
		t.Fatalf("context-free digit run over-masked: %q", masked)
	}
}

// An IBAN names one person's account. Presidio's built-in recogniser validates the checksum, so a
// reference that merely looks IBAN-shaped is left alone.
func TestMaskTextLiveMasksAnIBAN(t *testing.T) {
	requireLivePresidio(t)

	masked, _, _, _ := maskText(context.Background(), "Please pay into GB82 WEST 1234 5698 7654 32 by Friday.")
	if strings.Contains(masked, "WEST") || strings.Contains(masked, "GB82") {
		t.Fatalf("IBAN leaked past masking: %q", masked)
	}
	if !strings.Contains(masked, "by Friday") {
		t.Fatalf("masking ate the sentence around the IBAN: %q", masked)
	}
}
