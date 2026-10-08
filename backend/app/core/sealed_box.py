"""AES-256-GCM sealing shared by stored Gmail tokens and personal-detail vaults.

Format 1: 0x01, a random 12-byte nonce, then ciphertext and tag; always the "legacy" key.
Format 2: 0x02, the key id's length (one byte), the key id, then format 1's nonce, ciphertext and tag.
Keys come from a keyring, "kid:base64key,kid2:base64key" with the first entry primary, plus the
single key from before rotation as kid "legacy". New values are always sealed in format 2 with the
primary key. Callers bind the record's identity as associated data, so a sealed value copied to
another record does not open. The listener's Go side (tokencrypt.go) reads and writes the same format.
"""

import base64
import binascii
import os
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

FORMAT_V1 = 0x01
FORMAT_V2 = 0x02
NONCE_BYTES = 12
KEY_BYTES = 32
MAX_KEY_ID_BYTES = 255
LEGACY_KEY_ID = "legacy"


class SealKeyError(RuntimeError):
    """The key settings are missing or malformed; never carries key material."""


class SealOpenError(RuntimeError):
    """The sealed value is corrupt, tampered with, sealed with an unknown key, or for another record."""


@dataclass(frozen=True)
class KeySettings:
    """The names of a keyring's two settings, for error messages."""

    ring: str
    legacy: str


@dataclass(frozen=True)
class Keyring:
    primary: str
    keys: dict[str, bytes]


def _decode_key(encoded: str, setting: str) -> bytes:
    try:
        key = base64.b64decode(encoded.strip(), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SealKeyError(f"{setting} is not valid base64") from exc
    if len(key) != KEY_BYTES:
        raise SealKeyError(f"{setting} must decode to {KEY_BYTES} bytes")
    return key


def _ring_entries(ring: str, setting: str) -> list[tuple[str, bytes]]:
    entries = []
    for entry in (part.strip() for part in ring.split(",")):
        if not entry:
            continue  # a trailing comma
        kid, separator, encoded = entry.partition(":")
        if not separator:
            raise SealKeyError(f"{setting}: an entry has no key id; write kid:base64key")
        if not kid or len(kid.encode()) > MAX_KEY_ID_BYTES:
            raise SealKeyError(f"{setting}: a key id must be 1 to {MAX_KEY_ID_BYTES} bytes")
        entries.append((kid, _decode_key(encoded, setting)))
    return entries


def parse_keyring(ring: str, legacy: str, settings: KeySettings) -> Keyring:
    keys: dict[str, bytes] = {}
    for kid, key in _ring_entries(ring, settings.ring):
        if kid in keys:
            raise SealKeyError(f"{settings.ring}: key id {kid!r} appears twice")
        keys[kid] = key
    if legacy.strip():
        legacy_key = _decode_key(legacy, settings.legacy)
        if keys.setdefault(LEGACY_KEY_ID, legacy_key) != legacy_key:
            raise SealKeyError(f"{settings.legacy} differs from the {LEGACY_KEY_ID!r} key in the keyring")
    if not keys:
        raise SealKeyError(f"no key configured: set {settings.ring} or {settings.legacy}")
    return Keyring(primary=next(iter(keys)), keys=keys)


def split_sealed(sealed: bytes) -> tuple[str, bytes]:
    """The key id a value was sealed with, and its nonce, ciphertext and tag."""
    if not sealed or sealed[0] not in (FORMAT_V1, FORMAT_V2):
        raise SealOpenError("unrecognised sealed format")
    kid, body = LEGACY_KEY_ID, sealed[1:]
    if sealed[0] == FORMAT_V2:
        length = sealed[1] if len(sealed) > 1 else 0
        if length == 0 or len(sealed) < 2 + length:
            raise SealOpenError("unrecognised sealed format")
        kid, body = sealed[2 : 2 + length].decode(errors="replace"), sealed[2 + length :]
    if len(body) <= NONCE_BYTES:
        raise SealOpenError("unrecognised sealed format")
    return kid, body


def seal(plaintext: bytes, aad: bytes, keyring: Keyring) -> bytes:
    kid = keyring.primary.encode()
    nonce = os.urandom(NONCE_BYTES)
    header = bytes([FORMAT_V2, len(kid)]) + kid + nonce
    return header + AESGCM(keyring.keys[keyring.primary]).encrypt(nonce, plaintext, aad)


def unseal(sealed: bytes, aad: bytes, keyring: Keyring) -> bytes:
    kid, body = split_sealed(sealed)
    key = keyring.keys.get(kid)
    if key is None:
        raise SealOpenError(f"sealed with key id {kid!r}, which the keyring does not hold")
    try:
        return AESGCM(key).decrypt(body[:NONCE_BYTES], body[NONCE_BYTES:], aad)
    except InvalidTag as exc:
        raise SealOpenError("sealed value failed authentication") from exc
