"""Fill thread identity for rows stored before migration 0009, so they appear in thread views.

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
from app.gmail_send import _headers_of

THREAD_HEADERS = ("Message-ID", "References")


async def main() -> None:
    filled = failed = 0
    async with get_sessionmaker()() as session, httpx.AsyncClient(timeout=30) as client:
        stmt = select(Message).where(Message.thread_id.is_(None), Message.gmail_message_id.is_not(None))
        for message in (await session.scalars(stmt)).all():
            try:
                headers = await _headers_of(client, message.gmail_message_id, THREAD_HEADERS)
            except httpx.HTTPError as exc:
                failed += 1
                print(f"  skipped {message.id}: {type(exc).__name__}")
                continue
            message.thread_id = headers.get("threadid")
            message.rfc822_message_id = headers.get("message-id")
            message.thread_refs = headers.get("references")
            filled += 1
        await session.commit()
    print(f"filled {filled}, skipped {failed}")


if __name__ == "__main__":
    asyncio.run(main())
