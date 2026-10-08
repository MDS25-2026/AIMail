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


async def _claim(where: ColumnElement[bool], order: tuple[ColumnElement, ...], limit: int | None) -> list[UUID]:
    queue = select(Message.id).where(where).order_by(*order).limit(limit).with_for_update(skip_locked=True)
    async with get_sessionmaker()() as session, session.begin():
        claimed = await session.scalars(update(Message).where(Message.id.in_(queue.scalar_subquery()))
                                        .values(generation_claimed_until=func.now() + GENERATION_LEASE)
                                        .returning(Message.id))
        return list(claimed)


async def claim_for_drafting(limit: int | None) -> list[UUID]:
    """Fewest attempts first, so a message that keeps failing sinks behind newer ones."""
    return await _claim(_draftable(), (Message.generation_attempts, Message.created_at.desc()), limit)


def is_requested() -> ColumnElement[bool]:
    """Opened by a person and not yet tried: only a first attempt is fast, so a failing draft falls back
    to the regular pass instead of being retried every few seconds."""
    return Message.draft_requested_at.is_not(None) & (Message.generation_attempts == 0)


async def claim_requested(limit: int) -> list[UUID]:
    """The emails people are waiting on, oldest request first."""
    return await _claim(_draftable() & is_requested(), (Message.draft_requested_at,), limit)


async def request_draft(pk: UUID) -> None:
    """Ask the worker for this email's draft; a second request keeps the first one's place."""
    async with get_sessionmaker()() as session, session.begin():
        await session.execute(update(Message).where(Message.id == pk, Message.draft_requested_at.is_(None),
                                                     _draftable()).values(draft_requested_at=func.now()))


async def release_drafting(pk: UUID) -> None:
    async with get_sessionmaker()() as session, session.begin():
        await session.execute(update(Message).where(Message.id == pk).values(generation_claimed_until=None))
