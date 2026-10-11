"""Backfill vector embeddings for stored masked emails (migration 0035, Issue #144).

Generates gemini-embedding-001 vectors (1536 dims, L2-normalized) for messages
where embedding IS NULL and body_masked IS NOT NULL.
Embeds each email through the model gateway (last masking check, egress record) and commits
per batch, so an interruption keeps its progress. Private mode users' emails are left out.

Usage (from backend/): python scripts/backfill_message_embeddings.py
"""

import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import model_gateway
from app.core.providers import Provider
from app.db.models import Message
from app.db.session import get_sessionmaker
from app.egress_log import save_egress
from app.private_mode import not_private
from app.rag.ingest import INDEX
from model_gateway import track_egress

BATCH_SIZE = 15


async def _embedded(message: Message, text: str) -> list[float]:
    """Through the model gateway, one email at a time: the last masking check runs, and what was
    sent is recorded against that email and its owner, as for every other model call."""
    with track_egress() as sent:
        [vector] = await model_gateway.embed_documents([text], provider=Provider.GEMINI, purpose=INDEX)
    await save_egress(sent, user_id=message.user_id, message_id=message.id)
    return vector


async def main() -> None:
    async with get_sessionmaker()() as session:
        stmt = (
            select(Message)
            .where(Message.embedding.is_(None), Message.body_masked.is_not(None), not_private(Message.user_id))
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
                for message, text in zip(batch, texts, strict=True):
                    message.embedding = await _embedded(message, text)
                await session.commit()
                filled += len(batch)
                print(f"  embedded {filled}/{total} messages")
            except Exception as exc:  # noqa: BLE001
                print(f"  batch {i}-{i+len(batch)} failed: {exc}")
                await session.rollback()

        print(f"Completed: successfully embedded {filled}/{total} messages.")


if __name__ == "__main__":
    asyncio.run(main())
