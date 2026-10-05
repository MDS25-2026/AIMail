package main

import (
	"encoding/base64"
	"encoding/json"
	"os"
	"testing"
)

type tokenVector struct {
	Key       string `json:"key"`
	UserID    string `json:"user_id"`
	Plaintext string `json:"plaintext"`
	Sealed    string `json:"sealed"`
}

func loadTokenVector(t *testing.T) tokenVector {
	t.Helper()
	raw, err := os.ReadFile("testdata/token_vector.json")
	if err != nil {
		t.Fatal(err)
	}
	var v tokenVector
	if err := json.Unmarshal(raw, &v); err != nil {
		t.Fatal(err)
	}
	return v
}

// The backend seals tokens in Python; the listener must read them byte for byte.
func TestTheBackendsSealedVectorDecrypts(t *testing.T) {
	v := loadTokenVector(t)
	sealed, _ := base64.StdEncoding.DecodeString(v.Sealed)
	got, err := unsealToken(v.Key, sealed, v.UserID)
	if err != nil || got != v.Plaintext {
		t.Fatalf("got %q, %v", got, err)
	}
}

// The user id is bound in, so a token copied to another user's row is useless to them.
func TestAVectorForAnotherUserDoesNotDecrypt(t *testing.T) {
	v := loadTokenVector(t)
	sealed, _ := base64.StdEncoding.DecodeString(v.Sealed)
	if _, err := unsealToken(v.Key, sealed, "someone-else"); err == nil {
		t.Fatal("decrypted for the wrong user")
	}
}

func TestATokenRoundTripsAndATamperedOneFails(t *testing.T) {
	v := loadTokenVector(t)
	sealed, err := sealToken(v.Key, "1//refresh", "user-a")
	if err != nil {
		t.Fatal(err)
	}
	if got, err := unsealToken(v.Key, sealed, "user-a"); err != nil || got != "1//refresh" {
		t.Fatalf("round trip: %q, %v", got, err)
	}
	sealed[len(sealed)-1] ^= 1
	if _, err := unsealToken(v.Key, sealed, "user-a"); err == nil {
		t.Fatal("tampered token decrypted")
	}
}

func TestAMissingOrShortKeyIsRefused(t *testing.T) {
	for _, key := range []string{"", "c2hvcnQ=", "not base64!!"} {
		if _, err := sealToken(key, "x", "user-a"); err == nil {
			t.Fatalf("key %q accepted", key)
		}
	}
}
