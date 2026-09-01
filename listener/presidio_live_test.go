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
	url := getEnvOrDefault("PRESIDIO_ANALYZER_URL", "http://localhost:5001/analyze")
	if _, err := presidioPost(ctx, url, []byte(`{"text":"ping","language":"en"}`)); err != nil {
		t.Skipf("presidio analyzer unreachable (%v) — start it: docker compose up -d", err)
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
