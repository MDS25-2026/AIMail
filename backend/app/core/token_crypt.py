"""Encryption for stored Google refresh tokens (specs/features/per-user-mailboxes.md).

AES-256-GCM. Sealed format: one version byte, a random 12-byte nonce, then ciphertext and tag. The
owner's user id is the associated data, so a sealed token copied to another user's row fails to
decrypt instead of granting that user someone else's mailbox. The listener's tokencrypt.go reads
the same format.
"""

import base64
import binascii
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings

FORMAT_VERSION = b"\x01"
NONCE_BYTES = 12
KEY_BYTES = 32
_AAD_PREFIX = "aimail-mailbox-token:v1:"


class TokenKeyError(RuntimeError):
    """TOKEN_ENCRYPTION_KEY is missing or not 32 base64-encoded bytes; nothing is sealed or read."""


class TokenDecryptError(RuntimeError):
    """The sealed token is corrupt, tampered with, or belongs to a different user."""


def _cipher() -> AESGCM:
    raw = get_settings().token_encryption_key.strip()
    try:
        key = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise TokenKeyError("TOKEN_ENCRYPTION_KEY is not valid base64") from exc
    if len(key) != KEY_BYTES:
        raise TokenKeyError(f"TOKEN_ENCRYPTION_KEY must decode to {KEY_BYTES} bytes")
    return AESGCM(key)


def _aad(user_id: str) -> bytes:
    return (_AAD_PREFIX + user_id).encode()


def seal(token: str, user_id: str) -> bytes:
    """The token encrypted for one owner, ready to store."""
    nonce = os.urandom(NONCE_BYTES)
    return FORMAT_VERSION + nonce + _cipher().encrypt(nonce, token.encode(), _aad(user_id))


def unseal(sealed: bytes, user_id: str) -> str:
    """The plaintext token, only for the owner it was sealed for."""
    cipher = _cipher()
    if len(sealed) <= 1 + NONCE_BYTES or sealed[:1] != FORMAT_VERSION:
        raise TokenDecryptError("unrecognised sealed token format")
    nonce, body = sealed[1 : 1 + NONCE_BYTES], sealed[1 + NONCE_BYTES :]
    try:
        return cipher.decrypt(nonce, body, _aad(user_id)).decode()
    except InvalidTag as exc:
        raise TokenDecryptError("sealed token failed authentication") from exc
