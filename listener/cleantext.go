package main

import "strings"

// Full-width forms of the characters phones, IC numbers and emails are made of, as Chinese mail often
// writes them (０１２-３４５６７８９); the regex floor only knows the plain ones. Chinese punctuation
// (，：（）) is left alone, and NFKC is not used: it would also rewrite m² and ½ (specs/features/normalisation-v2.md).
const (
	fullWidthOffset = 0xFEE0 // U+FF01..U+FF5E sit this far above U+0021..U+007E
	fullWidthPunct  = "＠．－＋＿"
)

// Characters with no width that split a name or a number apart for the masker.
var invisible = strings.NewReplacer("\u200b", "", "\u200c", "", "\u200d", "", "\u2060", "", "\xef\xbb\xbf", "")

// cleanText readies text for masking: full-width digits, letters and address punctuation made plain,
// invisible characters removed.
func cleanText(text string) string {
	return strings.Map(plainForm, invisible.Replace(text))
}

func plainForm(r rune) rune {
	isDigit := r >= '０' && r <= '９'
	isLetter := (r >= 'Ａ' && r <= 'Ｚ') || (r >= 'ａ' && r <= 'ｚ')
	if isDigit || isLetter || strings.ContainsRune(fullWidthPunct, r) {
		return r - fullWidthOffset
	}
	return r
}
