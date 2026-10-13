package main

import (
	"encoding/json"
	"strings"
	"testing"
)

func TestReprocessLeavesAloneWhatItMustNotTouch(t *testing.T) {
	sent := "2026-10-01T00:00:00Z"
	waiting := map[string]bool{"held": true}
	cases := []struct {
		row  reprocessRow
		want string
	}{
		{reprocessRow{ID: "a", SentAt: &sent, MaskingStatus: maskingComplete, HasBody: true}, skipReplied},
		{reprocessRow{ID: "b", MaskingStatus: maskingPending, HasBody: true}, skipNotComplete},
		{reprocessRow{ID: "c", MaskingStatus: maskingComplete}, skipPastRetention},
		{reprocessRow{ID: "held", MaskingStatus: maskingComplete, HasBody: true}, skipSendWaiting},
		{reprocessRow{ID: "d", MaskingStatus: maskingComplete, HasBody: true}, ""},
	}
	for _, c := range cases {
		if got := skipReason(c.row, waiting); got != c.want {
			t.Errorf("%s: got %q, want %q", c.row.ID, got, c.want)
		}
	}
}

// The old summary, items, draft and category were written in the old numbering, so all are cleared.
func TestReprocessClearsEverythingWrittenInTheOldNumbering(t *testing.T) {
	patch, err := json.Marshal(reprocessPatch{MaskedContent: MaskedContent{BodyMasked: "Hi [PERSON_1]"}, ActionItems: []string{}})
	if err != nil {
		t.Fatal(err)
	}
	text := string(patch)
	for _, cleared := range []string{`"draft_reply":""`, `"ai_summary":""`, `"action_items":[]`, `"category":null`,
		`"generated_at":null`, `"critic_checks":null`, `"generation_attempts":0`, `"language":null`, `"own_text_en":null`} {
		if !strings.Contains(text, cleared) {
			t.Errorf("%s not in %s", cleared, text)
		}
	}
}
