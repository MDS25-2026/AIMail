package main

// Restorable masking (specs/features/restorable-masking.md): each personal detail becomes a
// numbered placeholder such as [PERSON_1], the same value always the same number within an email,
// and the placeholder-to-value map is sealed into the email's row so the backend can show the
// owner the real details and fill them into an approved reply. The AI only ever sees placeholders.

import (
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"regexp"
	"strings"
	"sync"
	"unicode/utf8"
)

// detailKind is a placeholder family; the list matches backend/app/core/redaction.py DETAIL_KINDS.
type detailKind string

const (
	kindPerson   detailKind = "PERSON"
	kindEmail    detailKind = "EMAIL"
	kindPhone    detailKind = "PHONE"
	kindIC       detailKind = "IC"
	kindPassport detailKind = "PASSPORT"
	kindAccount  detailKind = "ACCOUNT"
	kindCard     detailKind = "CARD"
	kindLocation detailKind = "LOCATION"
	kindOrg      detailKind = "ORG"
)

const vaultAADPrefix = "aimail-pii-vault:v1:"

var placeholderRegex = regexp.MustCompile(`\[(PERSON|EMAIL|PHONE|IC|PASSPORT|ACCOUNT|CARD|LOCATION|ORG)_\d+\]`)

// Names are compared by words, ignoring case; numbers and addresses by their letters and digits,
// so "012-345 6789" and "0123456789" are one detail.
func normaliseDetail(kind detailKind, value string) string {
	if kind == kindPerson || kind == kindLocation || kind == kindOrg {
		return strings.Join(strings.Fields(strings.ToLower(value)), " ")
	}
	return strings.Map(func(r rune) rune {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') {
			return r
		}
		return -1
	}, strings.ToLower(value))
}

// detailVault numbers one email's details as they are masked.
type detailVault struct {
	counts  map[detailKind]int
	byValue map[string]string // kind + normalised value -> placeholder
	values  map[string]string // placeholder -> value as written
}

func newDetailVault() *detailVault {
	return &detailVault{counts: map[detailKind]int{}, byValue: map[string]string{}, values: map[string]string{}}
}

func (v *detailVault) placeholder(kind detailKind, value string) string {
	identity := string(kind) + "\x00" + normaliseDetail(kind, value)
	if known, ok := v.byValue[identity]; ok {
		return known
	}
	v.counts[kind]++
	placeholder := fmt.Sprintf("[%s_%d]", kind, v.counts[kind])
	v.byValue[identity] = placeholder
	v.values[placeholder] = strings.TrimSpace(value)
	return placeholder
}

// fork copies the vault, so text that may yet be dropped (attachment text without NER) cannot
// leave its details behind in the email's vault.
func (v *detailVault) fork() *detailVault {
	copied := newDetailVault()
	for k, n := range v.counts {
		copied.counts[k] = n
	}
	for k, p := range v.byValue {
		copied.byValue[k] = p
	}
	for p, value := range v.values {
		copied.values[p] = value
	}
	return copied
}

var warnNoVaultKey sync.Once

// sealed is the vault as PostgREST takes a bytea in JSON (`\x` then hex), or "" when there is
// nothing to keep or no key: the email is still masked, its details just cannot be restored.
func (v *detailVault) sealed(ownerID, gmailMessageID string) string {
	if len(v.values) == 0 {
		return ""
	}
	keys, isUsable := vaultKeyring()
	if !isUsable {
		return ""
	}
	plaintext, err := json.Marshal(v.values) // map keys marshal sorted, like the backend's
	if err != nil {
		log.Printf("could not encode the detail vault for %s: %v", gmailMessageID, err)
		return ""
	}
	sealed, err := keys.seal(plaintext, vaultAADPrefix+ownerID+":"+gmailMessageID)
	if err != nil {
		log.Printf("could not seal the detail vault for %s: %v", gmailMessageID, err)
		return ""
	}
	return `\x` + hex.EncodeToString(sealed)
}

// vaultKeyring is the vault keys, or false (said once) when none are set or they do not parse.
func vaultKeyring() (keyring, bool) {
	keys, err := vaultKeys.load()
	if err == nil {
		return keys, true
	}
	warnNoVaultKey.Do(func() {
		log.Printf("WARNING: %v; emails are masked but their details cannot be shown or restored", err)
	})
	return keyring{}, false
}

// runeSpans converts regexp byte offsets to rune offsets, the unit Presidio reports.
func runeSpans(text string, byteSpans [][]int) [][2]int {
	spans := make([][2]int, 0, len(byteSpans))
	for _, s := range byteSpans {
		spans = append(spans, [2]int{utf8.RuneCountInString(text[:s[0]]), utf8.RuneCountInString(text[:s[1]])})
	}
	return spans
}
