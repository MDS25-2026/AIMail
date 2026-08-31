package main

// R02 masking-recall harness. The proposal's Goal 3 sets an 80% PII identification target;
// this measures it against the labeled corpus in testdata/pii_fixtures.json rather than
// asserting it. Extend the fixtures, not this file.
//
// NER-layer cases need the Presidio containers. When they are unreachable the harness scores
// the regex layer alone and says so, so an offline number is never mistaken for the full one.

import (
	"context"
	"encoding/json"
	"os"
	"strings"
	"testing"
)

const recallTarget = 0.80

type piiCase struct {
	Name     string   `json:"name"`
	Text     string   `json:"text"`
	MustMask []string `json:"must_mask"`
	Layer    string   `json:"layer"`
}

type piiNegative struct {
	Name     string   `json:"name"`
	Text     string   `json:"text"`
	MustKeep []string `json:"must_keep"`
}

type piiFixtures struct {
	Cases     []piiCase     `json:"cases"`
	Negatives []piiNegative `json:"negatives"`
}

func loadFixtures(t *testing.T) piiFixtures {
	t.Helper()
	raw, err := os.ReadFile("testdata/pii_fixtures.json")
	if err != nil {
		t.Fatalf("read fixtures: %v", err)
	}
	var f piiFixtures
	if err := json.Unmarshal(raw, &f); err != nil {
		t.Fatalf("parse fixtures: %v", err)
	}
	return f
}

// presidioIsLive reports whether the NER layer can be scored in this run.
func presidioIsLive() bool {
	url := getEnvOrDefault("PRESIDIO_ANALYZER_URL", "http://localhost:5001/analyze")
	_, err := presidioPost(context.Background(), url, []byte(`{"text":"ping","language":"en"}`))
	return err == nil
}

func TestMaskingRecallMeetsTarget(t *testing.T) {
	fixtures := loadFixtures(t)
	live := presidioIsLive()

	var total, masked int
	var misses []string
	for _, c := range fixtures.Cases {
		if c.Layer == "ner" && !live {
			continue // scoring these without the containers would understate real recall
		}
		got, _, _, _ := maskText(context.Background(), c.Text)
		for _, want := range c.MustMask {
			total++
			if strings.Contains(got, want) {
				misses = append(misses, c.Name+": "+want)
				continue
			}
			masked++
		}
	}

	if total == 0 {
		t.Fatal("no fixture spans scored")
	}
	recall := float64(masked) / float64(total)
	scope := "regex + NER"
	if !live {
		scope = "regex only (Presidio unreachable)"
	}
	t.Logf("R02 recall: %d/%d spans = %.1f%% [%s]", masked, total, recall*100, scope)
	for _, m := range misses {
		t.Logf("  missed - %s", m)
	}
	if recall < recallTarget {
		t.Errorf("recall %.1f%% is below the %.0f%% target", recall*100, recallTarget*100)
	}
}

// Recall alone can be gamed by masking everything, which would gut draft quality and RAG
// text. Business numerals must survive untouched.
func TestMaskingLeavesBusinessTextIntact(t *testing.T) {
	fixtures := loadFixtures(t)
	for _, n := range fixtures.Negatives {
		t.Run(n.Name, func(t *testing.T) {
			got, _, _, _ := maskText(context.Background(), n.Text)
			for _, keep := range n.MustKeep {
				if !strings.Contains(got, keep) {
					t.Errorf("over-masked %q: %q", keep, got)
				}
			}
		})
	}
}
