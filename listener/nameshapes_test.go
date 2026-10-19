package main

import (
	"strings"
	"testing"
)

// The English model labels Malay prose as names (13 Oct: "Saya ingin", "cuti tahunan", "diserahkan").
func TestMalayProseIsNotAName(t *testing.T) {
	text := "Saya ingin memohon cuti tahunan. Kerja-kerja saya akan diserahkan kepada Farid. Yang benar,"
	hit := func(phrase string) presidioResult {
		start := len([]rune(text[:strings.Index(text, phrase)]))
		return presidioResult{EntityType: "PERSON", Start: start, End: start + len([]rune(phrase)), Score: 0.85}
	}
	results := []presidioResult{hit("Saya ingin"), hit("cuti tahunan"), hit("saya akan"), hit("diserahkan"), hit("Farid"), hit("Yang")}
	var kept []string
	runes := []rune(text)
	for _, r := range nameShapedOnly(text, results) {
		kept = append(kept, string(runes[r.Start:r.End]))
	}
	if strings.Join(kept, "|") != "Farid" {
		t.Fatalf("kept %q, want only Farid", kept)
	}
}

func TestANameKeepsItsParticlesAndLosesTheWordsAroundIt(t *testing.T) {
	text := "kepada Siti binti Ali dan Ludwig van Beethoven"
	r := presidioResult{EntityType: "PERSON", Start: 0, End: len([]rune(text)), Score: 0.85}
	var kept []string
	for _, run := range nameShapedOnly(text, []presidioResult{r}) {
		kept = append(kept, string([]rune(text)[run.Start:run.End]))
	}
	if strings.Join(kept, "|") != "Siti binti Ali|Ludwig van Beethoven" {
		t.Fatalf("got %q", kept)
	}
}

func TestChineseHitsAndOtherEntitiesPassThrough(t *testing.T) {
	text := "请联系陈伟明，电话 012-3456789"
	results := []presidioResult{
		{EntityType: "PERSON", Start: 3, End: 6, Score: 0.85},
		{EntityType: "PHONE_NUMBER", Start: 11, End: 22, Score: 0.9},
	}
	if got := nameShapedOnly(text, results); len(got) != 2 || got[0].End != 6 {
		t.Fatalf("got %+v", got)
	}
}

// Against the real analyzer: the email from the 13 Oct report, and a Chinese one.
func TestLiveMalayAndChineseMailIsMaskedWhereItShouldBe(t *testing.T) {
	requireLivePresidio(t)
	malay := "Salam sejahtera,\n\nSaya ingin memohon cuti tahunan dari 20 hingga 24 Oktober kerana ada urusan " +
		"keluarga di kampung. Boleh saya tahu berapa hari cuti tahunan saya yang masih berbaki tahun ini?\n\n" +
		"Kerja-kerja saya akan diserahkan kepada Farid sepanjang tempoh cuti.\n\nTerima kasih atas perhatian anda." +
		"\n\nYang benar,\nNurul Huda\nEksekutif Kewangan"
	masked, _, _, degraded := maskText(t.Context(), malay, newDetailVault())
	if degraded {
		t.Fatal("presidio degraded")
	}
	for _, kept := range []string{"cuti tahunan", "saya akan diserahkan", "perhatian anda", "Yang benar", "Saya ingin"} {
		if !strings.Contains(masked, kept) {
			t.Errorf("prose %q was masked: %q", kept, masked)
		}
	}
	for _, name := range []string{"Nurul Huda", "Farid"} {
		if strings.Contains(masked, name) {
			t.Errorf("name %q survived: %q", name, masked)
		}
	}
	chinese := "您好，\n\n我是陈伟明，想确认下周三的会议时间。请联系李美玲。\n\n谢谢，\n王小红"
	masked, _, _, _ = maskText(t.Context(), chinese, newDetailVault())
	for _, name := range []string{"陈伟明", "李美玲", "王小红"} {
		if strings.Contains(masked, name) {
			t.Errorf("name %q survived: %q", name, masked)
		}
	}
	if !strings.Contains(masked, "会议时间") || !strings.Contains(masked, "谢谢") {
		t.Errorf("prose was masked: %q", masked)
	}
}

func TestPlaceholderIsNotTreatedAsANameWord(t *testing.T) {
	for _, token := range []string{"PHONE_1", "EMAIL_1", "PERSON_2", "IC_1", "LOCATION_3", "ORG_1"} {
		if isNameWord(token) {
			t.Errorf("placeholder %q must not be considered a name word", token)
		}
	}
	text := "Aisyah Rahman [PHONE_1]"
	hit := presidioResult{EntityType: "PERSON", Start: 0, End: len([]rune("Aisyah Rahman")), Score: 0.85}
	runs := nameShapedOnly(text, []presidioResult{hit})
	if len(runs) != 1 || string([]rune(text)[runs[0].Start:runs[0].End]) != "Aisyah Rahman" {
		t.Fatalf("name adjacent to placeholder failed: %+v", runs)
	}
}
