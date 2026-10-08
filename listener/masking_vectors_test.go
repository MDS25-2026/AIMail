package main

import (
	"encoding/json"
	"os"
	"strings"
	"testing"
)

// The shared floor cases (testdata/masking_vectors.json); the backend's mask_typed_text reads the same file.
type maskingVectors struct {
	MustMask []struct{ Kind, Text, Secret string } `json:"must_mask"`
	MustKeep []struct{ Kind, Text, Keep string }   `json:"must_keep"`
}

func loadMaskingVectors(t *testing.T) maskingVectors {
	t.Helper()
	raw, err := os.ReadFile("testdata/masking_vectors.json")
	if err != nil {
		t.Fatal(err)
	}
	var vectors maskingVectors
	if err := json.Unmarshal(raw, &vectors); err != nil {
		t.Fatal(err)
	}
	return vectors
}

func TestTheSharedFloorCasesAreMasked(t *testing.T) {
	for _, c := range loadMaskingVectors(t).MustMask {
		masked, _, _ := maskPII(c.Text, newDetailVault())
		if strings.Contains(masked, c.Secret) {
			t.Errorf("%s: %q still in %q", c.Kind, c.Secret, masked)
		}
	}
}

func TestTheSharedFloorCasesThatAreNotDetailsAreKept(t *testing.T) {
	for _, c := range loadMaskingVectors(t).MustKeep {
		masked, _, _ := maskPII(c.Text, newDetailVault())
		if !strings.Contains(masked, c.Keep) {
			t.Errorf("%s: %q lost from %q", c.Kind, c.Keep, masked)
		}
	}
}
