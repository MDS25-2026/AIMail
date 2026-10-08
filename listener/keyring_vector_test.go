package main

// Cross-language keyring vectors: each side seals format 2 under two key ids (and "legacy"), copies
// in its format 1 vectors, and both sides must open both files.

import (
	"encoding/base64"
	"encoding/json"
	"os"
	"testing"
)

// Test-only keys: bytes 0x20..0x3f and 0x40..0x5f, never used for real data.
const (
	testKeyK1 = "ICEiIyQlJicoKSorLC0uLzAxMjM0NTY3ODk6Ozw9Pj8="
	testKeyK2 = "QEFCQ0RFRkdISUpLTE1OT1BRUlNUVVZXWFlaW1xdXl8="
)

const (
	keyringVectorGo     = "testdata/keyring_vector_go.json"
	keyringVectorPython = "testdata/keyring_vector_python.json"
	vectorOwner         = "aaaaaaaa-0000-4000-8000-000000000001"
)

type sealedTokenCase struct {
	KeyID     string `json:"kid"`
	Format    int    `json:"format"`
	UserID    string `json:"user_id"`
	Plaintext string `json:"plaintext"`
	Sealed    string `json:"sealed"` // base64
}

type sealedVaultCase struct {
	KeyID   string            `json:"kid"`
	Format  int               `json:"format"`
	Owner   string            `json:"owner"`
	GmailID string            `json:"gmail_message_id"`
	Details map[string]string `json:"details"`
	Sealed  string            `json:"sealed"` // base64
}

type keyringVector struct {
	Comment     string            `json:"_comment"`
	Ring        string            `json:"ring"`         // TOKEN_ENCRYPTION_KEYS and PII_VAULT_KEYS
	TokenLegacy string            `json:"token_legacy"` // TOKEN_ENCRYPTION_KEY
	VaultLegacy string            `json:"vault_legacy"` // PII_VAULT_KEY
	Tokens      []sealedTokenCase `json:"tokens"`
	Vaults      []sealedVaultCase `json:"vaults"`
}

func requireHeader(t *testing.T, sealed []byte, format int, kid string) {
	t.Helper()
	got, _, err := splitSealed(sealed)
	if err != nil || int(sealed[0]) != format || got != kid {
		t.Fatalf("want format %d kid %q, got format %d kid %q (%v)", format, kid, sealed[0], got, err)
	}
}

func openKeyringVector(t *testing.T, path string) {
	var vec keyringVector
	readJSON(t, path, &vec)
	tokens, vaults := mustKeyring(t, vec.Ring, vec.TokenLegacy), mustKeyring(t, vec.Ring, vec.VaultLegacy)
	for _, c := range vec.Tokens {
		sealed, _ := base64.StdEncoding.DecodeString(c.Sealed)
		requireHeader(t, sealed, c.Format, c.KeyID)
		if got, err := unsealToken(tokens, sealed, c.UserID); err != nil || got != c.Plaintext {
			t.Fatalf("token under %q: %q, %v", c.KeyID, got, err)
		}
	}
	for _, c := range vec.Vaults {
		sealed, _ := base64.StdEncoding.DecodeString(c.Sealed)
		requireHeader(t, sealed, c.Format, c.KeyID)
		plain, err := vaults.open(sealed, vaultAADPrefix+c.Owner+":"+c.GmailID)
		var details map[string]string
		if err != nil || json.Unmarshal(plain, &details) != nil || details["[PERSON_1]"] != c.Details["[PERSON_1]"] {
			t.Fatalf("vault under %q: %v, %v", c.KeyID, details, err)
		}
	}
}

func TestTheBackendsKeyringVectorOpensHere(t *testing.T) {
	openKeyringVector(t, keyringVectorPython)
}

func TestOurOwnKeyringVectorOpens(t *testing.T) {
	openKeyringVector(t, keyringVectorGo)
}

// Regenerates keyringVectorGo (run with WRITE_KEYRING_VECTOR=1); the backend's tests open it.
func TestWriteGoKeyringVector(t *testing.T) {
	if os.Getenv("WRITE_KEYRING_VECTOR") == "" {
		t.Skip("set WRITE_KEYRING_VECTOR=1 to regenerate " + keyringVectorGo)
	}
	token := loadTokenVector(t)
	var vault vaultVector
	readJSON(t, "testdata/vault_vector_go.json", &vault)
	ring := "k2:" + testKeyK2 + ",k1:" + testKeyK1
	vec := keyringVector{
		Comment: "Test-only keys, sealed by the listener's Go; never used for real data.",
		Ring:    ring, TokenLegacy: token.Key, VaultLegacy: vault.Key,
		Tokens: []sealedTokenCase{
			{KeyID: legacyKeyID, Format: formatV1, UserID: token.UserID, Plaintext: token.Plaintext, Sealed: token.Sealed},
			sealTokenCase(t, mustKeyring(t, ring, ""), "k2"),
			sealTokenCase(t, mustKeyring(t, "k1:"+testKeyK1, ""), "k1"),
			sealTokenCase(t, mustKeyring(t, "", token.Key), legacyKeyID),
		},
		Vaults: []sealedVaultCase{
			{KeyID: legacyKeyID, Format: formatV1, Owner: vault.Owner, GmailID: vault.GmailID, Details: vault.Details, Sealed: vault.Sealed},
			sealVaultCase(t, mustKeyring(t, "k1:"+testKeyK1, ""), vault.Details),
		},
	}
	out, _ := json.MarshalIndent(vec, "", "  ")
	if err := os.WriteFile(keyringVectorGo, append(out, '\n'), 0o644); err != nil {
		t.Fatal(err)
	}
}

func sealTokenCase(t *testing.T, kr keyring, kid string) sealedTokenCase {
	t.Helper()
	plaintext := "1//test-refresh-token-under-" + kid
	sealed, err := sealToken(kr, plaintext, vectorOwner)
	if err != nil {
		t.Fatal(err)
	}
	return sealedTokenCase{KeyID: kid, Format: formatV2, UserID: vectorOwner, Plaintext: plaintext,
		Sealed: base64.StdEncoding.EncodeToString(sealed)}
}

func sealVaultCase(t *testing.T, kr keyring, details map[string]string) sealedVaultCase {
	t.Helper()
	plaintext, _ := json.Marshal(details)
	sealed, err := kr.seal(plaintext, vaultAADPrefix+vectorOwner+":gm-keyring")
	if err != nil {
		t.Fatal(err)
	}
	return sealedVaultCase{KeyID: kr.primary, Format: formatV2, Owner: vectorOwner, GmailID: "gm-keyring",
		Details: details, Sealed: base64.StdEncoding.EncodeToString(sealed)}
}
