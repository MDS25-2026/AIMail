package main

// Stored Google refresh tokens, sealed by the backend (backend/app/core/token_crypt.py) and read
// here to watch each user's mailbox. AES-256-GCM; format: version byte, 12-byte nonce, ciphertext
// and tag; the owner's user id is the associated data, so a token copied to another user's row
// does not decrypt. Standard library only.

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

var errTokenFormat = errors.New("unrecognised sealed token format")

func tokenCipher(encodedKey string) (cipher.AEAD, error) {
	key, err := base64.StdEncoding.DecodeString(encodedKey)
	if err != nil {
		return nil, fmt.Errorf("TOKEN_ENCRYPTION_KEY is not valid base64: %w", err)
	}
	if len(key) != tokenKeyBytes {
		return nil, fmt.Errorf("TOKEN_ENCRYPTION_KEY must decode to %d bytes", tokenKeyBytes)
	}
	block, err := aes.NewCipher(key)
	if err != nil {
		return nil, err
	}
	return cipher.NewGCM(block)
}

func sealToken(encodedKey, token, userID string) ([]byte, error) {
	aead, err := tokenCipher(encodedKey)
	if err != nil {
		return nil, err
	}
	nonce := make([]byte, tokenNonceBytes)
	if _, err := rand.Read(nonce); err != nil {
		return nil, err
	}
	sealed := append([]byte{tokenFormatVersion}, nonce...)
	return aead.Seal(sealed, nonce, []byte(token), []byte(tokenAADPrefix+userID)), nil
}

func unsealToken(encodedKey string, sealed []byte, userID string) (string, error) {
	aead, err := tokenCipher(encodedKey)
	if err != nil {
		return "", err
	}
	if len(sealed) <= 1+tokenNonceBytes || sealed[0] != tokenFormatVersion {
		return "", errTokenFormat
	}
	nonce, body := sealed[1:1+tokenNonceBytes], sealed[1+tokenNonceBytes:]
	plain, err := aead.Open(nil, nonce, body, []byte(tokenAADPrefix+userID))
	if err != nil {
		return "", fmt.Errorf("sealed token failed authentication: %w", err)
	}
	return string(plain), nil
}
