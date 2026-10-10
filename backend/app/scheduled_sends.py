"""Send later, stored (specs/features/quiet-hours-send-later.md). The worker sends them
(app/scheduled_send_worker.py); this module only keeps the rows.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.dialects.postgresql import distinct_on, insert

from app.db.models import ScheduledSend
from app.db.session import get_sessionmaker


class CancelReason(StrEnum):
    CANCELLED = "cancelled"  # the user cancelled it
    THEY_REPLIED = "they_replied"  # a new message arrived in the thread first
    TOO_LATE = "too_late"  # due too long ago (the worker was down); sending now could land in quiet hours
    SENT_MANUALLY = "sent_manually"
    REFUSED = "refused"  # the send checks refused it when it fell due


# The ones the reader is told about, until they schedule or send again.
NOTICE_REASONS = (CancelReason.THEY_REPLIED, CancelReason.TOO_LATE, CancelReason.REFUSED)

_PENDING = and_(ScheduledSend.sent_at.is_(None), ScheduledSend.cancelled_reason.is_(None))


@dataclass(frozen=True)
class ScheduleState:
    send_at: datetime | None = None  # waiting to go out then
    cancelled: CancelReason | None = None  # the last one was cancelled for this, and nothing replaced it


async def hold(message_id: UUID, user_id: UUID | None, draft: str, send_at: datetime) -> None:
    """Hold this draft until send_at; a send already waiting for the email is replaced."""
    statement = insert(ScheduledSend).values(message_id=message_id, user_id=user_id, draft=draft, send_at=send_at)
    async with get_sessionmaker()() as session, session.begin():
        await session.execute(statement.on_conflict_do_update(
            index_elements=["message_id"], index_where=_PENDING, set_={"draft": draft, "send_at": send_at}))


async def cancel_pending(message_id: UUID, reason: CancelReason) -> bool:
    async with get_sessionmaker()() as session, session.begin():
        cancelled = await session.scalar(update(ScheduledSend).where(ScheduledSend.message_id == message_id, _PENDING)
                                         .values(cancelled_reason=reason).returning(ScheduledSend.id))
    return cancelled is not None


async def states_for(message_ids: list[UUID]) -> dict[UUID, ScheduleState]:
    """Each email's newest schedule, as the dashboard shows it."""
    if not message_ids:
        return {}
    newest = (select(ScheduledSend).where(ScheduledSend.message_id.in_(message_ids))
              .ext(distinct_on(ScheduledSend.message_id))
              .order_by(ScheduledSend.message_id, ScheduledSend.created_at.desc()))
    async with get_sessionmaker()() as session:
        rows = (await session.scalars(newest)).all()
    states = {}
    for row in rows:
        if row.sent_at is None and row.cancelled_reason is None:
            states[row.message_id] = ScheduleState(send_at=row.send_at)
        elif row.cancelled_reason in NOTICE_REASONS:
            states[row.message_id] = ScheduleState(cancelled=CancelReason(row.cancelled_reason))
    return states


async def due(now: datetime) -> list[ScheduledSend]:
    async with get_sessionmaker()() as session:
        return list((await session.scalars(
            select(ScheduledSend).where(_PENDING, ScheduledSend.send_at <= now))).all())


async def claim(schedule_id: UUID) -> bool:
    """Claim-then-send, as approve_and_send does: two workers can never both send it."""
    async with get_sessionmaker()() as session, session.begin():
        claimed = await session.scalar(update(ScheduledSend).where(ScheduledSend.id == schedule_id, _PENDING)
                                       .values(sent_at=datetime.now().astimezone()).returning(ScheduledSend.id))
    return claimed is not None


async def release(schedule_id: UUID) -> None:
    async with get_sessionmaker()() as session, session.begin():
        await session.execute(update(ScheduledSend).where(ScheduledSend.id == schedule_id).values(sent_at=None))


async def cancel(schedule_id: UUID, reason: CancelReason) -> None:
    async with get_sessionmaker()() as session, session.begin():
        await session.execute(update(ScheduledSend).where(ScheduledSend.id == schedule_id, _PENDING)
                              .values(cancelled_reason=reason))


async def cancel_claimed(schedule_id: UUID, reason: CancelReason) -> None:
    """A claimed send the checks refused: not sent after all, and the reader is told why."""
    async with get_sessionmaker()() as session, session.begin():
        await session.execute(update(ScheduledSend).where(ScheduledSend.id == schedule_id)
                              .values(sent_at=None, cancelled_reason=reason))
