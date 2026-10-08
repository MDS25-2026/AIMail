package main

import (
	"encoding/base64"
	"encoding/json"
	"errors"
	"os"
	"strings"
	"testing"
)

type tokenVector struct {
	Key       string `json:"key"`
	UserID    string `json:"user_id"`
	Plaintext string `json:"plaintext"`
	Sealed    string `json:"sealed"`
}

func readJSON(t *testing.T, path string, into any) {
	t.Helper()
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if err := json.Unmarshal(raw, into); err != nil {
		t.Fatal(err)
	}
}

func loadTokenVector(t *testing.T) tokenVector {
	t.Helper()
	var v tokenVector
	readJSON(t, "testdata/token_vector.json", &v)
	return v
}

func mustKeyring(t *testing.T, ring, legacy string) keyring {
	t.Helper()
	kr, err := tokenKeys.parse(ring, legacy)
	if err != nil {
		t.Fatal(err)
	}
	return kr
}

// Format 1, sealed by the backend in Python before key ids existed; it opens with the legacy key.
func TestTheBackendsFormatOneVectorOpensWithTheLegacyKey(t *testing.T) {
	v := loadTokenVector(t)
	sealed, _ := base64.StdEncoding.DecodeString(v.Sealed)
	got, err := unsealToken(mustKeyring(t, "", v.Key), sealed, v.UserID)
	if err != nil || got != v.Plaintext {
		t.Fatalf("got %q, %v", got, err)
	}
}

// The user id is bound in, so a token copied to another user's row is useless to them.
func TestAVectorForAnotherUserDoesNotDecrypt(t *testing.T) {
	v := loadTokenVector(t)
	sealed, _ := base64.StdEncoding.DecodeString(v.Sealed)
	if _, err := unsealToken(mustKeyring(t, "", v.Key), sealed, "someone-else"); err == nil {
		t.Fatal("decrypted for the wrong user")
	}
}

func TestATokenRoundTripsAndATamperedOneFails(t *testing.T) {
	kr := mustKeyring(t, "", loadTokenVector(t).Key)
	sealed, err := sealToken(kr, "1//refresh", "user-a")
	if err != nil {
		t.Fatal(err)
	}
	if got, err := unsealToken(kr, sealed, "user-a"); err != nil || got != "1//refresh" {
		t.Fatalf("round trip: %q, %v", got, err)
	}
	sealed[len(sealed)-1] ^= 1
	if _, err := unsealToken(kr, sealed, "user-a"); err == nil {
		t.Fatal("tampered token decrypted")
	}
}

func TestNewSealsUseFormatTwoAndThePrimaryKey(t *testing.T) {
	kr := mustKeyring(t, "k2:"+testKeyK2+",k1:"+testKeyK1, loadTokenVector(t).Key)
	sealed, err := sealToken(kr, "1//refresh", "user-a")
	if err != nil {
		t.Fatal(err)
	}
	if kid, _, err := splitSealed(sealed); err != nil || sealed[0] != formatV2 || kid != "k2" {
		t.Fatalf("want format 2 under k2, got format %d kid %q (%v)", sealed[0], kid, err)
	}
	old := mustKeyring(t, "k1:"+testKeyK1, "")
	if _, err := unsealToken(old, sealed, "user-a"); !errors.Is(err, errUnknownKeyID) {
		t.Fatalf("a keyring without k2 must say so, got %v", err)
	}
}

func TestABadKeyringIsRefusedWithoutEchoingKeys(t *testing.T) {
	cases := map[string][2]string{
		"nothing set":            {"", ""},
		"short key":              {"", "c2hvcnQ="},
		"not base64":             {"", "not base64!!"},
		"entry without a kid":    {testKeyK1, ""},
		"empty kid":              {":" + testKeyK1, ""},
		"duplicate kid":          {"k1:" + testKeyK1 + ",k1:" + testKeyK2, ""},
		"kid too long":           {strings.Repeat("k", maxKeyIDBytes+1) + ":" + testKeyK1, ""},
		"two different legacies": {"legacy:" + testKeyK1, testKeyK2},
	}
	for name, settings := range cases {
		t.Run(name, func(t *testing.T) {
			_, err := tokenKeys.parse(settings[0], settings[1])
			if err == nil {
				t.Fatal("accepted")
			}
			if strings.Contains(err.Error(), testKeyK1) || strings.Contains(err.Error(), testKeyK2) {
				t.Fatalf("the error leaks a key: %v", err)
			}
		})
	}
}

func TestTheLegacyKeyMayAlsoBeNamedInTheRing(t *testing.T) {
	kr := mustKeyring(t, "k2:"+testKeyK2+",legacy:"+testKeyK1, testKeyK1)
	if kr.primary != "k2" || len(kr.keys) != 2 {
		t.Fatalf("got primary %q and %d keys", kr.primary, len(kr.keys))
	}
}
