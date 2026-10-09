package main

// Live integration tests for the Presidio NER layer. Each test exercises maskText against
// the real analyzer/anonymizer containers and skips itself when they are unreachable, so
// `go test` stays green offline while the NER claims remain verifiable locally
// (docker compose up -d from the repo root).

import (
	"context"
	"os"
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
		failIfPresidioRequired(t)
		t.Skip("presidio analyzer or anonymizer unreachable — start them: docker compose up -d")
	}
}

// failIfPresidioRequired stops a run that must score the NER layer (CI sets REQUIRE_PRESIDIO) from
// passing by skipping it when the containers did not come up.
func failIfPresidioRequired(t *testing.T) {
	t.Helper()
	if os.Getenv("REQUIRE_PRESIDIO") != "" {
		t.Fatal("REQUIRE_PRESIDIO is set but the presidio analyzer or anonymizer is unreachable")
	}
}

func TestMaskTextLiveMasksNamesAndLocations(t *testing.T) {
	requireLivePresidio(t)

	masked, _, _, degraded := maskText(context.Background(), "Please ask Sarah Tan in Kuala Lumpur to reply to the vendor.", newDetailVault())

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

	masked, _, _, degraded := maskText(context.Background(), "Wire the deposit to my Maybank account 512837465920 by Friday.", newDetailVault())

	if degraded {
		t.Fatal("degraded=true with a live analyzer")
	}
	if strings.Contains(masked, "512837465920") {
		t.Fatalf("context-flanked account number leaked: %q", masked)
	}
}

func TestMaskTextLiveLeavesContextFreeDigitRun(t *testing.T) {
	requireLivePresidio(t)

	masked, _, _, _ := maskText(context.Background(), "We shipped 93842716 widgets on Friday.", newDetailVault())

	if !strings.Contains(masked, "93842716") {
		t.Fatalf("context-free digit run over-masked: %q", masked)
	}
}

// An IBAN names one person's account. Presidio's built-in recogniser validates the checksum, so a
// reference that merely looks IBAN-shaped is left alone.
func TestMaskTextLiveMasksAnIBAN(t *testing.T) {
	requireLivePresidio(t)

	masked, _, _, _ := maskText(context.Background(), "Please pay into GB82 WEST 1234 5698 7654 32 by Friday.", newDetailVault())
	if strings.Contains(masked, "WEST") || strings.Contains(masked, "GB82") {
		t.Fatalf("IBAN leaked past masking: %q", masked)
	}
	if !strings.Contains(masked, "by Friday") {
		t.Fatalf("masking ate the sentence around the IBAN: %q", masked)
	}
}

// Plates, postcodes and grouped bank numbers are gated on nearby words like accounts are: both sides
// of each gate are tested, since the false positives (amounts, URLs, "Q3") are what the gate is for.
func TestMaskTextLiveMasksPlatesPostcodesAndGroupedAccounts(t *testing.T) {
	requireLivePresidio(t)
	cases := []struct{ text, raw string }{
		{"Please transfer to my Maybank account 5141 2345 6789 by Friday.", "5141 2345 6789"},
		{"Deliver to No 12, Jalan Bukit 3, Taman Melawati, 53100 Kuala Lumpur.", "53100"},
		{"My car plate is WXY 1234, parked at level 2.", "WXY 1234"},
	}
	for _, c := range cases {
		masked, _, _, degraded := maskText(context.Background(), c.text, newDetailVault())
		if degraded || strings.Contains(masked, c.raw) {
			t.Errorf("%q leaked (degraded=%v): %q", c.raw, degraded, masked)
		}
	}
}

func TestMaskTextLiveLeavesLookalikesWithoutContext(t *testing.T) {
	requireLivePresidio(t)
	for _, text := range []string{
		"See PR 196 and Q3 results; invoice 48213 attached.",
		"Total due is 15000 for 30 units.",
		"Read it at https://e.example.com/c3/869:6abd25 on our platform.",
		"Our Customer Care Team at the R2 desk will call.",
	} {
		masked, _, _, _ := maskText(context.Background(), text, newDetailVault())
		if masked != text {
			t.Errorf("masked a lookalike: %q -> %q", text, masked)
		}
	}
}
