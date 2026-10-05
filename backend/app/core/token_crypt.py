"""Encryption for stored Google refresh tokens (specs/features/per-user-mailboxes.md).

AES-256-GCM via app/core/sealed_box.py. The owner's user id is the associated data, so a sealed
token copied to another user's row fails to decrypt instead of granting that user someone else's
mailbox. The listener's tokencrypt.go reads the same format.
"""

from app.core import sealed_box
from app.core.config import get_settings

_AAD_PREFIX = "aimail-mailbox-token:v1:"
_SETTING = "TOKEN_ENCRYPTION_KEY"


class TokenKeyError(RuntimeError):
    """TOKEN_ENCRYPTION_KEY is missing or not 32 base64-encoded bytes; nothing is sealed or read."""


class TokenDecryptError(RuntimeError):
    """The sealed token is corrupt, tampered with, or belongs to a different user."""


def _aad(user_id: str) -> bytes:
    return (_AAD_PREFIX + user_id).encode()


def seal(token: str, user_id: str) -> bytes:
    """The token encrypted for one owner, ready to store."""
    try:
        return sealed_box.seal(token.encode(), _aad(user_id), get_settings().token_encryption_key, _SETTING)
    except sealed_box.SealKeyError as exc:
        raise TokenKeyError(str(exc)) from exc


def unseal(sealed: bytes, user_id: str) -> str:
    """The plaintext token, only for the owner it was sealed for."""
    try:
        return sealed_box.unseal(sealed, _aad(user_id), get_settings().token_encryption_key, _SETTING).decode()
    except sealed_box.SealKeyError as exc:
        raise TokenKeyError(str(exc)) from exc
    except sealed_box.SealOpenError as exc:
        raise TokenDecryptError(str(exc)) from exc
