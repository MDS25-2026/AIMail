"""Re-seal stored Gmail tokens and detail vaults under the primary key after a key rotation.

Rotation: put the new key first in TOKEN_ENCRYPTION_KEYS / PII_VAULT_KEYS and keep the old one in
the ring (or in TOKEN_ENCRYPTION_KEY / PII_VAULT_KEY, read as kid "legacy"), deploy the backend and
listener, run this with --apply, then drop the old key. A dry run (the default) only counts.

Each row is written only if it still holds the value that was read, so a user reconnecting or a vault
being emptied meanwhile is never overwritten. Prints ids and counts only, never a secret.

Usage (from backend/): python scripts/reseal_secrets.py [--apply]
"""

import argparse
import asyncio
import sys
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core import sealed_box, token_crypt, vault
from app.db.models import MailboxConnection, Message
from app.db.session import get_sessionmaker

_OPEN_ERRORS = (sealed_box.SealOpenError, token_crypt.TokenDecryptError, vault.VaultUnavailableError)


@dataclass
class Tally:
    resealed: int = 0
    current: int = 0
    failed: int = 0

    def line(self, what: str, is_applied: bool) -> str:
        verb = "resealed" if is_applied else "to reseal"
        return f"{what}: {self.resealed} {verb}, {self.current} already on the primary key, {self.failed} failed"


def reseal_token(sealed: bytes, user_id: str, primary: str) -> bytes | None:
    """The token under the primary key, or None when it already is."""
    if sealed_box.split_sealed(sealed)[0] == primary:
        return None
    return token_crypt.seal(token_crypt.unseal(sealed, user_id), user_id)


def reseal_vault(sealed: bytes, owner_id: UUID | None, gmail_message_id: str, primary: str) -> bytes | None:
    """The vault under the primary key, or None when it already is."""
    if sealed_box.split_sealed(sealed)[0] == primary:
        return None
    return vault.seal_vault(vault.open_vault(sealed, owner_id, gmail_message_id), owner_id, gmail_message_id)


def _count(tally: Tally, label: str, reseal: Callable[[], bytes | None]) -> bytes | None:
    try:
        resealed = reseal()
    except _OPEN_ERRORS as exc:
        tally.failed += 1
        print(f"  {label} not resealed: {type(exc).__name__}")
        return None
    if resealed is None:
        tally.current += 1
        return None
    tally.resealed += 1
    return resealed


async def _reseal_tokens(session: AsyncSession, is_applied: bool) -> Tally:
    tally, primary = Tally(), token_crypt.keyring().primary
    rows = (await session.execute(select(MailboxConnection.user_id, MailboxConnection.refresh_token_encrypted))).all()
    for user_id, sealed in rows:
        resealed = _count(tally, f"token of user {user_id}", partial(reseal_token, sealed, str(user_id), primary))
        if resealed is None or not is_applied:
            continue
        await session.execute(update(MailboxConnection)
                              .where(MailboxConnection.user_id == user_id,
                                     MailboxConnection.refresh_token_encrypted == sealed)
                              .values(refresh_token_encrypted=resealed))
        await session.commit()
    return tally


async def _reseal_vaults(session: AsyncSession, is_applied: bool) -> Tally:
    tally, primary = Tally(), vault.keyring().primary
    stmt = select(Message.id, Message.user_id, Message.gmail_message_id, Message.pii_vault).where(
        Message.pii_vault.is_not(None))
    for message_id, owner_id, gmail_id, sealed in (await session.execute(stmt)).all():
        resealed = _count(tally, f"vault of message {message_id}",
                          partial(reseal_vault, sealed, owner_id, gmail_id or "", primary))
        if resealed is None or not is_applied:
            continue
        await session.execute(update(Message).where(Message.id == message_id, Message.pii_vault == sealed)
                              .values(pii_vault=resealed))
        await session.commit()
    return tally


async def main(is_applied: bool) -> int:
    async with get_sessionmaker()() as session:
        tokens = await _reseal_tokens(session, is_applied)
        vaults = await _reseal_vaults(session, is_applied)
    print(tokens.line("tokens", is_applied))
    print(vaults.line("vaults", is_applied))
    if not is_applied:
        print("dry run: nothing was written; run again with --apply")
    return 1 if tokens.failed or vaults.failed else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--apply", action="store_true", help="write the resealed values (default: count only)")
    sys.exit(asyncio.run(main(parser.parse_args().apply)))
