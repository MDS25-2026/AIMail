package main

import (
	"strings"
	"testing"
)

func TestFullWidthPhonesAndEmailsAreMaskedLikePlainOnes(t *testing.T) {
	for _, text := range []string{"请致电 ０１２-３４５６７８９", "电邮 ａｌｉ＠ｍａｉｌ．ｃｏｍ 谢谢"} {
		masked, _, _ := maskPII(cleanText(text), newDetailVault())
		if !strings.Contains(masked, "[PHONE_") && !strings.Contains(masked, "[EMAIL_") {
			t.Errorf("not masked: %q -> %q", text, masked)
		}
	}
}

func TestChinesePunctuationAndUnitsAreLeftAsWritten(t *testing.T) {
	text := "您好，面积是 5 m²，约 ½ 层（二楼）。"
	if got := cleanText(text); got != text {
		t.Fatalf("changed: %q", got)
	}
}

func TestInvisibleCharactersNoLongerSplitWords(t *testing.T) {
	if got := cleanText("Nur\u200bul Hu\xef\xbb\xbfda"); got != "Nurul Huda" {
		t.Fatalf("got %q", got)
	}
}

func TestNonAsciiSpacesAreFoldedForPhoneMasking(t *testing.T) {
	for _, text := range []string{"012\u00a03456789", "012\u30003456789", "012\u202f3456789"} {
		masked, _, _ := maskPII(cleanText(text), newDetailVault())
		if !strings.Contains(masked, "[PHONE_") {
			t.Errorf("phone with non-ASCII space not masked: %q -> %q", text, masked)
		}
	}
}
