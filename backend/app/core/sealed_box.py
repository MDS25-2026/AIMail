"""AES-256-GCM sealing shared by stored Gmail tokens and personal-detail vaults.

Sealed format: one version byte, a random 12-byte nonce, then ciphertext and tag. Callers bind the
record's identity as associated data, so a sealed value copied to another record does not open.
The listener's Go side (tokencrypt.go) reads and writes the same format.
"""

import base64
import binascii
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

FORMAT_VERSION = b"\x01"
NONCE_BYTES = 12
KEY_BYTES = 32


class SealKeyError(RuntimeError):
    """The key setting is missing or not 32 base64-encoded bytes."""


class SealOpenError(RuntimeError):
    """The sealed value is corrupt, tampered with, or belongs to another record."""


def _cipher(encoded_key: str, setting: str) -> AESGCM:
    try:
        key = base64.b64decode(encoded_key.strip(), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SealKeyError(f"{setting} is not valid base64") from exc
    if len(key) != KEY_BYTES:
        raise SealKeyError(f"{setting} must decode to {KEY_BYTES} bytes")
    return AESGCM(key)


def seal(plaintext: bytes, aad: bytes, encoded_key: str, setting: str) -> bytes:
    nonce = os.urandom(NONCE_BYTES)
    return FORMAT_VERSION + nonce + _cipher(encoded_key, setting).encrypt(nonce, plaintext, aad)


def unseal(sealed: bytes, aad: bytes, encoded_key: str, setting: str) -> bytes:
    cipher = _cipher(encoded_key, setting)
    if len(sealed) <= 1 + NONCE_BYTES or sealed[:1] != FORMAT_VERSION:
        raise SealOpenError("unrecognised sealed format")
    nonce, body = sealed[1 : 1 + NONCE_BYTES], sealed[1 + NONCE_BYTES :]
    try:
        return cipher.decrypt(nonce, body, aad)
    except InvalidTag as exc:
        raise SealOpenError("sealed value failed authentication") from exc
