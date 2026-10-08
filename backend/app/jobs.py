"""Claiming work, so background jobs are safe however many workers run (2026-10-08 audit).

A job takes rows with an UPDATE over a FOR UPDATE SKIP LOCKED select: two workers never take the same row,
and each row carries a lease, so a worker that dies mid-draft frees its rows when the lease runs out.
"""

from datetime import timedelta
from uuid import UUID

from sqlalchemy import ColumnElement, func, or_, select, update

from app.db.models import Message
from app.db.session import get_sessionmaker
from app.email_policy import drafting_filter

# A message whose drafting fails this many times is left for a human instead of being retried
# every poll cycle, which would spend quota and hold back the messages behind it.
MAX_GENERATION_ATTEMPTS = 5
# Longer than one draft can take (the dashboard's agent timeout is 120 s).
GENERATION_LEASE = timedelta(minutes=3)


def _draftable() -> ColumnElement[bool]:
    unclaimed = or_(Message.generation_claimed_until.is_(None), Message.generation_claimed_until < func.now())
    return (Message.generated_at.is_(None) & drafting_filter()
            & (Message.generation_attempts < MAX_GENERATION_ATTEMPTS) & unclaimed)


async def claim_for_drafting(limit: int | None) -> list[UUID]:
    """Fewest attempts first, so a message that keeps failing sinks behind newer ones."""
    queue = (select(Message.id).where(_draftable())
             .order_by(Message.generation_attempts, Message.created_at.desc())
             .limit(limit).with_for_update(skip_locked=True))
    async with get_sessionmaker()() as session, session.begin():
        claimed = await session.scalars(update(Message).where(Message.id.in_(queue.scalar_subquery()))
                                        .values(generation_claimed_until=func.now() + GENERATION_LEASE)
                                        .returning(Message.id))
        return list(claimed)


async def claim_one_for_drafting(pk: UUID) -> bool:
    """For drafting on open: False when another worker is already drafting it."""
    async with get_sessionmaker()() as session, session.begin():
        claimed = await session.scalar(update(Message).where(Message.id == pk, _draftable())
                                       .values(generation_claimed_until=func.now() + GENERATION_LEASE)
                                       .returning(Message.id))
    return claimed is not None


async def release_drafting(pk: UUID) -> None:
    async with get_sessionmaker()() as session, session.begin():
        await session.execute(update(Message).where(Message.id == pk).values(generation_claimed_until=None))
