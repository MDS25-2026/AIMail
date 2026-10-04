"""Fill thread identity and Reply-To for rows stored before migrations 0009 and 0014.

Reads only the threading headers from Gmail (format=metadata), never a body. Idempotent: rows that
already have a thread_id are skipped, so re-running costs nothing.

Usage (from backend/): python scripts/backfill_thread_ids.py
"""

import asyncio
import sys
from pathlib import Path

import httpx
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.models import Message
from app.db.session import get_sessionmaker
from app.gmail_send import message_headers

THREAD_HEADERS = ("Message-ID", "References", "Reply-To")


async def main() -> None:
    """Commits per row, so an interruption keeps what was already filled."""
    filled = failed = 0
    async with get_sessionmaker()() as session, httpx.AsyncClient(timeout=30) as client:
        stmt = select(Message).where(
            (Message.thread_id.is_(None)) | (Message.reply_to.is_(None)),
            Message.gmail_message_id.is_not(None),
        )
        for message in (await session.scalars(stmt)).all():
            try:
                headers = await message_headers(client, message.gmail_message_id, THREAD_HEADERS)
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                failed += 1
                print(f"  skipped {message.id}: {type(exc).__name__}")
                continue
            message.thread_id = message.thread_id or headers.get("threadid")
            message.rfc822_message_id = message.rfc822_message_id or headers.get("message-id")
            message.thread_refs = message.thread_refs or headers.get("references")
            # "" records "checked, none set", so a rerun does not fetch the row again.
            message.reply_to = message.reply_to or headers.get("reply-to") or ""
            await session.commit()
            filled += 1
    print(f"filled {filled}, skipped {failed}")


if __name__ == "__main__":
    asyncio.run(main())
