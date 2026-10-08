"""Encryption for stored Google refresh tokens (specs/features/per-user-mailboxes.md).

AES-256-GCM via app/core/sealed_box.py, with keys from TOKEN_ENCRYPTION_KEYS (and the older single
TOKEN_ENCRYPTION_KEY as kid "legacy"). The owner's user id is the associated data, so a sealed
token copied to another user's row fails to decrypt instead of granting that user someone else's
mailbox. The listener's tokencrypt.go reads the same format.
"""

from app.core import sealed_box
from app.core.config import get_settings

_AAD_PREFIX = "aimail-mailbox-token:v1:"
SETTINGS = sealed_box.KeySettings(ring="TOKEN_ENCRYPTION_KEYS", legacy="TOKEN_ENCRYPTION_KEY")


class TokenKeyError(RuntimeError):
    """No usable token key is configured; nothing is sealed or read."""


class TokenDecryptError(RuntimeError):
    """The sealed token is corrupt, tampered with, under an unknown key, or for a different user."""


def _aad(user_id: str) -> bytes:
    return (_AAD_PREFIX + user_id).encode()


def keyring() -> sealed_box.Keyring:
    settings = get_settings()
    try:
        return sealed_box.parse_keyring(settings.token_encryption_keys, settings.token_encryption_key, SETTINGS)
    except sealed_box.SealKeyError as exc:
        raise TokenKeyError(str(exc)) from exc


def seal(token: str, user_id: str) -> bytes:
    """The token encrypted for one owner with the primary key, ready to store."""
    return sealed_box.seal(token.encode(), _aad(user_id), keyring())


def unseal(sealed: bytes, user_id: str) -> str:
    """The plaintext token, only for the owner it was sealed for."""
    try:
        return sealed_box.unseal(sealed, _aad(user_id), keyring()).decode()
    except sealed_box.SealOpenError as exc:
        raise TokenDecryptError(str(exc)) from exc
