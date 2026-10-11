"""Move stored drafts onto the fixed owner and sender placeholders (2026-10-11).

Before, the owner's sign-off name and the sender's name were numbered after every person in the
thread, so a newer message naming someone new shifted them: an older email's stored draft that
signed off [PERSON_2] then restored as that new person. They now have fixed numbers
([PERSON_900], [PERSON_901]). This rewrites each stored draft's old numbers to the fixed ones,
working out what they were from the thread as it stood when the draft was written.

Only a number the old scheme newly allocated for the name is rewritten. When the name was already
someone in the thread, that number still means them and is left alone.

Nothing detected is printed: counts and short ids only. Dry run by default; --apply writes.
Sent rows are reported and left alone unless --include-sent: their draft is the record of what
went out, and renumbering changes its placeholders, not what it says.

Usage (from backend/):
    python scripts/renumber_sign_offs.py
    python scripts/renumber_sign_offs.py --apply
"""

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from email.utils import parseaddr
from pathlib import Path

from sqlalchemy import select, update

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.ownership import Scope
from app.core.redaction import PLACEHOLDER
from app.core.vault import (
    OWNER_PLACEHOLDER,
    SENDER_PLACEHOLDER,
    ThreadMap,
    VaultUnavailableError,
    open_vault,
)
from app.db.models import MaskingStatus, Message, UserProfile
from app.db.session import get_engine, get_sessionmaker

_EPOCH = datetime.min.replace(tzinfo=timezone.utc)

ThreadEntry = tuple[str, dict[str, str] | None, str]  # message key, its opened vault, its text


def renumbered(draft: str, thread: list[ThreadEntry], owner_name: str, sender_name: str) -> str:
    """The draft with the old owner and sender numbers swapped for the fixed ones."""
    if OWNER_PLACEHOLDER in draft or SENDER_PLACEHOLDER in draft:
        return draft  # written under the fixed numbers already
    old = ThreadMap()
    for key, values, text in thread:
        old.add_message(key, values, text)
    swaps: dict[str, str] = {}
    if owner_name.strip():
        placeholder, is_new = old.legacy_name_placeholder(owner_name)
        if is_new:
            swaps[placeholder] = OWNER_PLACEHOLDER
    if sender_name.strip():
        placeholder, is_new = old.legacy_name_placeholder(sender_name)
        if is_new:
            swaps[placeholder] = SENDER_PLACEHOLDER
    return PLACEHOLDER.sub(lambda match: swaps.get(match.group(0), match.group(0)), draft)


def _opened(message: Message) -> dict[str, str] | None:
    if message.pii_vault is None:
        return None
    try:
        return open_vault(message.pii_vault, message.user_id, message.gmail_message_id or "")
    except VaultUnavailableError:
        return None


def _entry(message: Message) -> ThreadEntry:
    text = f"{message.subject or ''}\n{message.snippet_masked or ''}\n{message.body_masked or ''}"
    return str(message.id), _opened(message), text


def _arrival(message: Message) -> datetime:
    return message.received_at or message.created_at or _EPOCH


async def _thread_when_written(session, message: Message) -> list[ThreadEntry]:
    """The thread as the draft saw it: messages stored by the time it was written, oldest first."""
    written = message.generated_at or message.created_at
    others = []
    if message.thread_id:
        others = (await session.scalars(select(Message).where(
            Message.thread_id == message.thread_id,
            Scope(owner_id=message.user_id).where(Message.user_id),
            Message.id != message.id,
            Message.masking_status == MaskingStatus.COMPLETE,
            Message.created_at <= written,
        ))).all()
    return [_entry(m) for m in sorted([*others, message], key=_arrival)]


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the renumbered drafts")
    parser.add_argument("--include-sent", action="store_true", help="also renumber sent rows' drafts")
    args = parser.parse_args()

    async with get_sessionmaker()() as session:
        drafts = (await session.scalars(select(Message).where(
            Message.draft_reply.like("%[PERSON_%"), Message.masking_status == MaskingStatus.COMPLETE))).all()
        names = dict((await session.execute(select(UserProfile.id, UserProfile.display_name))).all())
        changes, sent_changes, unchanged = [], 0, 0
        for message in drafts:
            new = renumbered(message.draft_reply, await _thread_when_written(session, message),
                             names.get(message.user_id) or "", parseaddr(message.from_addr or "")[0])
            if new == message.draft_reply:
                unchanged += 1
                continue
            is_sent = message.sent_at is not None
            sent_changes += is_sent
            print(f"  {str(message.id)[:8]}  {'sent' if is_sent else 'unsent'}")
            if args.include_sent or not is_sent:
                changes.append((message.id, new))
    print(f"{len(drafts)} draft(s) with a person placeholder: {unchanged} already right, "
          f"{len(changes) + (0 if args.include_sent else sent_changes)} to renumber "
          f"({sent_changes} of them sent{'' if args.include_sent else ', left alone without --include-sent'})")
    if not args.apply:
        print("dry run: nothing written. --apply renumbers the listed unsent drafts.")
        return
    async with get_sessionmaker()() as session, session.begin():
        for message_id, new in changes:
            await session.execute(update(Message).where(Message.id == message_id).values(draft_reply=new))
    print(f"renumbered {len(changes)} draft(s)")


async def _run() -> None:
    try:
        await main()
    finally:
        await get_engine().dispose()


if __name__ == "__main__":
    asyncio.run(_run())
