package main

import (
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"os"
	"strings"
	"testing"
)

const testVaultKey = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8="

// The same detail is one placeholder everywhere in an email, however it is written.
func TestOneDetailKeepsOnePlaceholderAcrossAnEmail(t *testing.T) {
	v := newDetailVault()
	first, _, _ := maskPII("call 012-345 6789 or mail a.b@corp.com", v)
	second, _, _ := maskPII("again: 0123456789, A.B@Corp.com, or 019-888 7777", v)
	if first != "call [PHONE_1] or mail [EMAIL_1]" {
		t.Fatalf("first: %q", first)
	}
	if second != "again: [PHONE_1], [EMAIL_1], or [PHONE_2]" {
		t.Fatalf("second: %q", second)
	}
	if v.values["[PHONE_1]"] != "012-345 6789" || v.values["[PHONE_2]"] != "019-888 7777" {
		t.Fatalf("values: %v", v.values)
	}
}

func TestNamesMatchAcrossCaseAndSpacing(t *testing.T) {
	v := newDetailVault()
	a := v.placeholder(kindPerson, "Aisyah Rahman")
	b := v.placeholder(kindPerson, "aisyah   RAHMAN")
	c := v.placeholder(kindPerson, "Ali")
	if a != b || a == c || c != "[PERSON_2]" {
		t.Fatalf("got %s %s %s", a, b, c)
	}
}

// Presidio reports character offsets; a name after non-ASCII text must still be cut exactly.
func TestEntitiesAreNumberedInReadingOrder(t *testing.T) {
	text := "Ali met Mei Ling"
	results := []presidioResult{{EntityType: "PERSON", Start: 8, End: 16, Score: 0.9}, {EntityType: "PERSON", Start: 0, End: 3, Score: 0.9}}
	if got := replaceEntities(text, results, newDetailVault()); got != "[PERSON_1] met [PERSON_2]" {
		t.Fatalf("got %q", got)
	}
}

func TestEntitiesAreReplacedByCharacterOffsetLongestFirst(t *testing.T) {
	text := "致 Aisyah Rahman of Kuala Lumpur, phone [PHONE_1]"
	results := []presidioResult{
		{EntityType: "PERSON", Start: 2, End: 8, Score: 0.9},  // "Aisyah", inside the longer match
		{EntityType: "PERSON", Start: 2, End: 15, Score: 0.8}, // "Aisyah Rahman"
		{EntityType: "LOCATION", Start: 19, End: 31, Score: 0.9},
		{EntityType: "ORGANIZATION", Start: 39, End: 48, Score: 0.9}, // overlaps the existing placeholder
	}
	v := newDetailVault()
	got := replaceEntities(text, results, v)
	if got != "致 [PERSON_1] of [LOCATION_1], phone [PHONE_1]" {
		t.Fatalf("got %q", got)
	}
	if v.values["[PERSON_1]"] != "Aisyah Rahman" || v.values["[LOCATION_1]"] != "Kuala Lumpur" {
		t.Fatalf("values: %v", v.values)
	}
}

// Attachment text dropped for lack of NER must not leave its details in the email's vault.
func TestDroppedAttachmentTextLeavesNothingInTheVault(t *testing.T) {
	t.Setenv("PRESIDIO_ANALYZER_URL", "http://127.0.0.1:1/analyze")
	v := newDetailVault()
	v.placeholder(kindPerson, "Aisyah")
	masked, _, _ := maskAttachmentText(t.Context(), messageRef{msgID: "m1"}, "IC 880101-14-5523", v)
	if masked != "" || len(v.values) != 1 {
		t.Fatalf("masked %q, vault %v", masked, v.values)
	}
}

func openVault(t *testing.T, sealedHex, ownerID, gmailID string) (map[string]string, error) {
	t.Helper()
	raw, err := hex.DecodeString(strings.TrimPrefix(sealedHex, `\x`))
	if err != nil {
		t.Fatal(err)
	}
	kr, err := vaultKeys.parse("", testVaultKey)
	if err != nil {
		t.Fatal(err)
	}
	plain, err := kr.open(raw, vaultAADPrefix+ownerID+":"+gmailID)
	if err != nil {
		return nil, err
	}
	var details map[string]string
	return details, json.Unmarshal(plain, &details)
}

func TestTheVaultIsSealedForItsOwnEmailOnly(t *testing.T) {
	t.Setenv(vaultKeys.ring, "")
	t.Setenv(vaultKeys.legacy, testVaultKey)
	v := newDetailVault()
	v.placeholder(kindPerson, "Aisyah")
	sealed := v.sealed("owner-1", "gm-1")
	if !strings.HasPrefix(sealed, `\x`) {
		t.Fatalf("not in PostgREST bytea form: %q", sealed[:4])
	}
	if got, err := openVault(t, sealed, "owner-1", "gm-1"); err != nil || got["[PERSON_1]"] != "Aisyah" {
		t.Fatalf("own email: %v %v", got, err)
	}
	if _, err := openVault(t, sealed, "owner-1", "gm-2"); err == nil {
		t.Fatal("opened for another email")
	}
}

func TestNoKeyOrNoDetailsStoresNoVault(t *testing.T) {
	t.Setenv(vaultKeys.ring, "")
	t.Setenv(vaultKeys.legacy, testVaultKey)
	if newDetailVault().sealed("o", "gm") != "" {
		t.Fatal("an empty vault was stored")
	}
	t.Setenv(vaultKeys.legacy, "")
	v := newDetailVault()
	v.placeholder(kindPerson, "Aisyah")
	if v.sealed("o", "gm") != "" {
		t.Fatal("stored without a key")
	}
}

type vaultVector struct {
	Key     string            `json:"key"`
	Owner   string            `json:"owner"`
	GmailID string            `json:"gmail_message_id"`
	Details map[string]string `json:"details"`
	Sealed  string            `json:"sealed"` // base64
}

// Sealed by the backend's Python; must open here, byte for byte the same format and AAD.
func TestAVaultSealedByTheBackendOpensHere(t *testing.T) {
	raw, err := os.ReadFile("testdata/vault_vector_python.json")
	if err != nil {
		t.Fatal(err)
	}
	var vec vaultVector
	if err := json.Unmarshal(raw, &vec); err != nil {
		t.Fatal(err)
	}
	sealed, _ := base64.StdEncoding.DecodeString(vec.Sealed)
	got, err := openVault(t, `\x`+hex.EncodeToString(sealed), vec.Owner, vec.GmailID)
	if err != nil || got["[PERSON_1]"] != vec.Details["[PERSON_1]"] {
		t.Fatalf("got %v, %v", got, err)
	}
}
