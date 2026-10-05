package main

// AES-256-GCM sealing shared with the backend (backend/app/core/sealed_box.py): a version byte, a
// 12-byte nonce, then ciphertext and tag. Callers bind the record's identity as associated data, so
// a sealed value copied to another record does not open. Used for stored Google refresh tokens
// (read here to watch each mailbox) and for each email's personal-detail vault (written here).

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"encoding/base64"
	"errors"
	"fmt"
)

const (
	tokenFormatVersion = 0x01
	tokenNonceBytes    = 12
	tokenKeyBytes      = 32
	tokenAADPrefix     = "aimail-mailbox-token:v1:"
)

var errTokenFormat = errors.New("unrecognised sealed format")

func aeadFor(encodedKey, setting string) (cipher.AEAD, error) {
	key, err := base64.StdEncoding.DecodeString(encodedKey)
	if err != nil {
		return nil, fmt.Errorf("%s is not valid base64: %w", setting, err)
	}
	if len(key) != tokenKeyBytes {
		return nil, fmt.Errorf("%s must decode to %d bytes", setting, tokenKeyBytes)
	}
	block, err := aes.NewCipher(key)
	if err != nil {
		return nil, err
	}
	return cipher.NewGCM(block)
}

func sealWith(encodedKey, setting string, plaintext []byte, aad string) ([]byte, error) {
	aead, err := aeadFor(encodedKey, setting)
	if err != nil {
		return nil, err
	}
	nonce := make([]byte, tokenNonceBytes)
	if _, err := rand.Read(nonce); err != nil {
		return nil, err
	}
	sealed := append([]byte{tokenFormatVersion}, nonce...)
	return aead.Seal(sealed, nonce, plaintext, []byte(aad)), nil
}

func openWith(encodedKey, setting string, sealed []byte, aad string) ([]byte, error) {
	aead, err := aeadFor(encodedKey, setting)
	if err != nil {
		return nil, err
	}
	if len(sealed) <= 1+tokenNonceBytes || sealed[0] != tokenFormatVersion {
		return nil, errTokenFormat
	}
	nonce, body := sealed[1:1+tokenNonceBytes], sealed[1+tokenNonceBytes:]
	plain, err := aead.Open(nil, nonce, body, []byte(aad))
	if err != nil {
		return nil, fmt.Errorf("sealed value failed authentication: %w", err)
	}
	return plain, nil
}

func sealToken(encodedKey, token, userID string) ([]byte, error) {
	return sealWith(encodedKey, "TOKEN_ENCRYPTION_KEY", []byte(token), tokenAADPrefix+userID)
}

func unsealToken(encodedKey string, sealed []byte, userID string) (string, error) {
	plain, err := openWith(encodedKey, "TOKEN_ENCRYPTION_KEY", sealed, tokenAADPrefix+userID)
	return string(plain), err
}
