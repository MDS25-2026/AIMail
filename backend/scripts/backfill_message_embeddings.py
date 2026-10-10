"""Backfill vector embeddings for stored masked emails (migration 0035, Issue #144).

Generates gemini-embedding-001 vectors (1536 dims, L2-normalized) for messages
where embedding IS NULL and body_masked IS NOT NULL.
Batches requests and commits per batch so interruptions retain progress.

Usage (from backend/): python scripts/backfill_message_embeddings.py
"""

import asyncio
import sys
from pathlib import Path

from sqlalchemy import ColumnElement, or_, select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.providers import Provider
from app.db.models import Message, UserPreferences
from app.db.session import get_sessionmaker
from app.rag.embed import embed_documents

BATCH_SIZE = 15


def _not_private() -> ColumnElement[bool]:
    """Private mode users' emails never go to Gemini, so they get no Gemini vector."""
    private_users = select(UserPreferences.user_id).where(UserPreferences.draft_provider == Provider.LOCAL)
    return or_(Message.user_id.is_(None), Message.user_id.not_in(private_users))


async def main() -> None:
    async with get_sessionmaker()() as session:
        stmt = (
            select(Message)
            .where(Message.embedding.is_(None), Message.body_masked.is_not(None), _not_private())
            .order_by(Message.received_at.desc().nulls_last())
        )
        messages = (await session.scalars(stmt)).all()
        total = len(messages)
        if total == 0:
            print("No messages require embedding backfill.")
            return

        print(f"Found {total} messages to embed in batches of {BATCH_SIZE}...")
        filled = 0
        for i in range(0, total, BATCH_SIZE):
            batch = messages[i : i + BATCH_SIZE]
            texts = [
                f"{m.subject or ''}\n\n{m.body_masked or m.snippet_masked or ''}".strip()
                for m in batch
            ]
            # Replace empty text with a fallback subject or spacer
            texts = [t if t else "No content" for t in texts]

            try:
                vectors = await embed_documents(texts)
                for message, vector in zip(batch, vectors, strict=True):
                    message.embedding = vector
                await session.commit()
                filled += len(batch)
                print(f"  embedded {filled}/{total} messages")
            except Exception as exc:  # noqa: BLE001
                print(f"  batch {i}-{i+len(batch)} failed: {exc}")
                await session.rollback()

        print(f"Completed: successfully embedded {filled}/{total} messages.")


if __name__ == "__main__":
    asyncio.run(main())
