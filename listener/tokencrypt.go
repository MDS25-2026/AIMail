package main

// AES-256-GCM sealing shared with the backend (backend/app/core/sealed_box.py). Callers bind the
// record's identity as associated data, so a sealed value copied to another record does not open.
// Used for stored Google refresh tokens (read here to watch each mailbox) and for each email's
// personal-detail vault (written here).
//
// Format 1: 0x01, 12-byte nonce, ciphertext and tag; always the "legacy" key.
// Format 2: 0x02, key-id length (1 byte), key id, then format 1's nonce, ciphertext and tag.

import (
	"bytes"
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"encoding/base64"
	"errors"
	"fmt"
	"os"
	"strings"
)

const (
	formatV1        = 0x01
	formatV2        = 0x02
	tokenNonceBytes = 12
	tokenKeyBytes   = 32
	maxKeyIDBytes   = 255
	legacyKeyID     = "legacy"
	keyringEntries  = ","
	keyIDSeparator  = ":"
	tokenAADPrefix  = "aimail-mailbox-token:v1:"
)

var (
	errTokenFormat  = errors.New("unrecognised sealed format")
	errNoKeys       = errors.New("no key configured")
	errUnknownKeyID = errors.New("sealed with a key id this keyring does not hold")
)

// keySettings names a keyring's two settings: the ring "kid:base64,kid2:base64" (first is primary)
// and the single key from before rotation, which is the "legacy" kid.
type keySettings struct {
	ring   string
	legacy string
}

var (
	tokenKeys = keySettings{ring: "TOKEN_ENCRYPTION_KEYS", legacy: "TOKEN_ENCRYPTION_KEY"}
	vaultKeys = keySettings{ring: "PII_VAULT_KEYS", legacy: "PII_VAULT_KEY"}
)

type keyring struct {
	primary string
	keys    map[string][]byte
}

func (s keySettings) load() (keyring, error) {
	return s.parse(os.Getenv(s.ring), os.Getenv(s.legacy))
}

// parse never puts key material in an error: only setting names and key ids.
func (s keySettings) parse(ring, legacy string) (keyring, error) {
	kr := keyring{keys: map[string][]byte{}}
	for _, entry := range strings.Split(ring, keyringEntries) {
		if strings.TrimSpace(entry) == "" {
			continue // a trailing comma
		}
		kid, encoded, isPair := strings.Cut(strings.TrimSpace(entry), keyIDSeparator)
		if !isPair {
			return keyring{}, fmt.Errorf("%s: an entry has no key id; write kid:base64key", s.ring)
		}
		if err := kr.add(kid, encoded, s.ring); err != nil {
			return keyring{}, err
		}
	}
	if err := kr.addLegacy(legacy, s.legacy); err != nil {
		return keyring{}, err
	}
	if kr.primary == "" {
		return keyring{}, fmt.Errorf("%w: set %s or %s", errNoKeys, s.ring, s.legacy)
	}
	return kr, nil
}

func (kr *keyring) add(kid, encoded, setting string) error {
	if kid == "" || len(kid) > maxKeyIDBytes {
		return fmt.Errorf("%s: a key id must be 1 to %d bytes", setting, maxKeyIDBytes)
	}
	if _, isTaken := kr.keys[kid]; isTaken {
		return fmt.Errorf("%s: key id %q appears twice", setting, kid)
	}
	key, err := decodeKey(encoded, setting)
	if err != nil {
		return err
	}
	kr.keys[kid] = key
	if kr.primary == "" {
		kr.primary = kid
	}
	return nil
}

// addLegacy adds the old single key as "legacy", unless the ring already names that same key.
func (kr *keyring) addLegacy(encoded, setting string) error {
	if strings.TrimSpace(encoded) == "" {
		return nil
	}
	existing, isNamed := kr.keys[legacyKeyID]
	if !isNamed {
		return kr.add(legacyKeyID, encoded, setting)
	}
	key, err := decodeKey(encoded, setting)
	if err != nil {
		return err
	}
	if !bytes.Equal(key, existing) {
		return fmt.Errorf("%s differs from the %q key in the keyring", setting, legacyKeyID)
	}
	return nil
}

func decodeKey(encoded, setting string) ([]byte, error) {
	key, err := base64.StdEncoding.DecodeString(strings.TrimSpace(encoded))
	if err != nil {
		return nil, fmt.Errorf("%s is not valid base64", setting)
	}
	if len(key) != tokenKeyBytes {
		return nil, fmt.Errorf("%s must decode to %d bytes", setting, tokenKeyBytes)
	}
	return key, nil
}

func aeadFor(key []byte) (cipher.AEAD, error) {
	block, err := aes.NewCipher(key)
	if err != nil {
		return nil, err
	}
	return cipher.NewGCM(block)
}

// seal always writes format 2 with the primary key; the associated data is the same in both formats.
func (kr keyring) seal(plaintext []byte, aad string) ([]byte, error) {
	aead, err := aeadFor(kr.keys[kr.primary])
	if err != nil {
		return nil, err
	}
	nonce := make([]byte, tokenNonceBytes)
	if _, err := rand.Read(nonce); err != nil {
		return nil, err
	}
	sealed := append([]byte{formatV2, byte(len(kr.primary))}, kr.primary...)
	sealed = append(sealed, nonce...)
	return aead.Seal(sealed, nonce, plaintext, []byte(aad)), nil
}

func (kr keyring) open(sealed []byte, aad string) ([]byte, error) {
	kid, body, err := splitSealed(sealed)
	if err != nil {
		return nil, err
	}
	key, isHeld := kr.keys[kid]
	if !isHeld {
		return nil, fmt.Errorf("%w: %q", errUnknownKeyID, kid)
	}
	aead, err := aeadFor(key)
	if err != nil {
		return nil, err
	}
	plain, err := aead.Open(nil, body[:tokenNonceBytes], body[tokenNonceBytes:], []byte(aad))
	if err != nil {
		return nil, fmt.Errorf("sealed value failed authentication: %w", err)
	}
	return plain, nil
}

// splitSealed reads the header: the key id it was sealed with, and the nonce, ciphertext and tag.
func splitSealed(sealed []byte) (string, []byte, error) {
	if len(sealed) == 0 {
		return "", nil, errTokenFormat
	}
	kid, body := legacyKeyID, sealed[1:]
	switch sealed[0] {
	case formatV1:
	case formatV2:
		if len(sealed) < 2 || sealed[1] == 0 || len(sealed) < 2+int(sealed[1]) {
			return "", nil, errTokenFormat
		}
		kid, body = string(sealed[2:2+int(sealed[1])]), sealed[2+int(sealed[1]):]
	default:
		return "", nil, errTokenFormat
	}
	if len(body) <= tokenNonceBytes {
		return "", nil, errTokenFormat
	}
	return kid, body, nil
}

func sealToken(kr keyring, token, userID string) ([]byte, error) {
	return kr.seal([]byte(token), tokenAADPrefix+userID)
}

func unsealToken(kr keyring, sealed []byte, userID string) (string, error) {
	plain, err := kr.open(sealed, tokenAADPrefix+userID)
	return string(plain), err
}
