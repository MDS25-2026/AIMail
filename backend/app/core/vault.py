"""Personal details hidden from the AI, kept per email in an encrypted vault (restorable masking).

The listener replaces each detail with a numbered placeholder such as [PERSON_1] and seals the
placeholder-to-value map with PII_VAULT_KEY, bound to the owner and Gmail id. Here the backend opens
the vaults of a thread and builds one ThreadMap: the same person keeps one number across every
message, the dashboard can show the owner the real details, typed text can be turned back into
placeholders before it reaches the AI, and an approved reply can be filled in at send time.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

from app.core import sealed_box
from app.core.config import get_settings
from app.core.redaction import PLACEHOLDER
from app.core.typed_text import mask_typed_text

logger = logging.getLogger(__name__)

_AAD_PREFIX = "aimail-pii-vault:v1:"
_SETTING = "PII_VAULT_KEY"


class DetailKind(StrEnum):
    PERSON = "PERSON"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    IC = "IC"
    PASSPORT = "PASSPORT"
    ACCOUNT = "ACCOUNT"
    CARD = "CARD"
    LOCATION = "LOCATION"
    ORG = "ORG"

# Compared case-insensitively and by words; everything else is compared by its letters and digits.
_WORDLIKE = {DetailKind.PERSON, DetailKind.LOCATION, DetailKind.ORG}


class VaultUnavailableError(RuntimeError):
    """The key is missing or the vault does not open for this email; its details stay hidden."""


def _aad(owner_id: UUID | None, gmail_message_id: str) -> bytes:
    return f"{_AAD_PREFIX}{owner_id or ''}:{gmail_message_id}".encode()


def seal_vault(details: dict[str, str], owner_id: UUID | None, gmail_message_id: str) -> bytes:
    """The listener's job; here for tests and the shared vector."""
    plaintext = json.dumps(details, ensure_ascii=False, sort_keys=True).encode()
    try:
        return sealed_box.seal(plaintext, _aad(owner_id, gmail_message_id), get_settings().pii_vault_key, _SETTING)
    except sealed_box.SealKeyError as exc:
        raise VaultUnavailableError(str(exc)) from exc


def open_vault(sealed: bytes, owner_id: UUID | None, gmail_message_id: str) -> dict[str, str]:
    try:
        raw = sealed_box.unseal(sealed, _aad(owner_id, gmail_message_id), get_settings().pii_vault_key, _SETTING)
    except (sealed_box.SealKeyError, sealed_box.SealOpenError) as exc:
        raise VaultUnavailableError(str(exc)) from exc
    details = json.loads(raw)
    return {key: value for key, value in details.items() if PLACEHOLDER.fullmatch(key) and isinstance(value, str)}


def _normalise(kind: DetailKind, value: str) -> str:
    if kind in _WORDLIKE:
        return " ".join(value.casefold().split())
    return re.sub(r"[^0-9a-z]", "", value.casefold())


@dataclass
class ThreadMap:
    """Thread-wide placeholders. Numbers are given in order of first appearance and never change."""

    values: dict[str, str | None] = field(default_factory=dict)
    _by_value: dict[tuple[DetailKind, str], str] = field(default_factory=dict)
    _local: dict[str, dict[str, str]] = field(default_factory=dict)  # message key -> local -> thread
    _counts: dict[DetailKind, int] = field(default_factory=dict)
    # The mailbox owner's name as a placeholder, for the reply's sign-off; None when unknown.
    owner: str | None = None

    def _allocate(self, kind: DetailKind, identity: str, value: str | None) -> str:
        known = self._by_value.get((kind, identity))
        if known:
            return known
        self._counts[kind] = self._counts.get(kind, 0) + 1
        placeholder = f"[{kind}_{self._counts[kind]}]"
        self._by_value[(kind, identity)] = placeholder
        self.values[placeholder] = value
        return placeholder

    def add_message(self, key: str, details: dict[str, str] | None, text: str) -> None:
        """Map one message's own numbering into the thread's. Without its vault, its placeholders
        get thread numbers of their own with no value, so they can never borrow another detail."""
        local = {}
        for match in sorted({m.group(0) for m in PLACEHOLDER.finditer(text)} | set(details or {}),
                            key=lambda p: (p.split("_")[0], int(PLACEHOLDER.fullmatch(p).group(2)))):
            kind = DetailKind(PLACEHOLDER.fullmatch(match).group(1))
            value = (details or {}).get(match)
            identity = _normalise(kind, value) if value else f"unknown:{key}:{match}"
            local[match] = self._allocate(kind, identity, value)
        self._local[key] = local

    def renumber(self, key: str, text: str) -> str:
        """A message's text in thread numbering; all placeholders swap at once, never in a chain."""
        local = self._local.get(key, {})
        return PLACEHOLDER.sub(lambda m: local.get(m.group(0), m.group(0)), text)

    def add_owner(self, name: str) -> str | None:
        """The mailbox owner's own name as a placeholder, so the AI can sign off without seeing it."""
        if not name.strip():
            return None
        self.owner = self._allocate(DetailKind.PERSON, _normalise(DetailKind.PERSON, name), name.strip())
        return self.owner

    def details(self) -> list[dict[str, str]]:
        return [{"placeholder": placeholder, "value": value, "kind": PLACEHOLDER.fullmatch(placeholder).group(1)}
                for placeholder, value in self.values.items() if value]

    def tokenise_known(self, text: str) -> str:
        """Every known value back into its placeholder, longest first, as whole words."""
        known = sorted(((p, v) for p, v in self.values.items() if v), key=lambda item: -len(item[1]))
        for placeholder, value in known:
            kind = DetailKind(PLACEHOLDER.fullmatch(placeholder).group(1))
            flags = re.IGNORECASE if kind in _WORDLIKE else 0
            pattern = r"(?<!\w)" + r"\s+".join(map(re.escape, value.split())) + r"(?!\w)"
            text = re.sub(pattern, placeholder, text, flags=flags)
        return text

    def for_model(self, typed: str) -> str:
        """Text a person typed, made safe for the AI: known details become placeholders, and any
        new fixed-format detail is masked as typed text always was."""
        return mask_typed_text(self.tokenise_known(typed))

    def restore(self, text: str) -> tuple[str, list[str]]:
        """Placeholders filled in for sending, and those with no value (which must stop the send)."""
        unresolved = sorted({m.group(0) for m in PLACEHOLDER.finditer(text) if not self.values.get(m.group(0))})
        return PLACEHOLDER.sub(lambda m: self.values.get(m.group(0)) or m.group(0), text), unresolved


def build_thread_map(messages: list[tuple[str, bytes | None, UUID | None, str, str]], owner_name: str) -> ThreadMap:
    """One numbering for a conversation. Each message is (key, sealed vault, owner, Gmail id, text),
    oldest first; a vault that does not open leaves that message's placeholders without values."""
    thread = ThreadMap()
    for key, sealed, owner_id, gmail_message_id, text in messages:
        details = None
        if sealed is not None:
            try:
                details = open_vault(sealed, owner_id, gmail_message_id)
            except VaultUnavailableError as exc:
                logger.warning("vault for message %s did not open: %s", key, exc)
        thread.add_message(key, details, text)
    thread.add_owner(owner_name)
    return thread
