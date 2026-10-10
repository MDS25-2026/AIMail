"""Sends held replies when due (specs/features/quiet-hours-send-later.md).

Each one is checked again first: a new message in the thread, or the owner's own answer from Gmail,
cancels it, so nobody answers twice or answers a question that was already moved on from; and one
missed by more than an hour (the worker was down) is cancelled rather than sent late into the quiet
hours it was meant to avoid. The send itself is
approve_and_send, with every check an approved reply gets.
"""

import logging
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from uuid import UUID

import httpx
from sqlalchemy import exists, select

from app.audit import AuditAction, audit
from app.core.constants import SCHEDULED_SEND_LATE_MINUTES
from app.core.errors import DomainError, ErrorCode
from app.core.ownership import Scope
from app.dashboard import approve_and_send
from app.db.models import Message, ScheduledSend
from app.db.session import get_sessionmaker
from app.gmail_send import (
    GmailAccessError,
    SendError,
    SendOutcomeUnknownError,
    sent_message_in_thread_since,
)
from app.scheduled_sends import (
    CancelReason,
    cancel,
    cancel_claimed,
    claim,
    due,
    release,
)

logger = logging.getLogger(__name__)

LATE_LIMIT = timedelta(minutes=SCHEDULED_SEND_LATE_MINUTES)


class Verdict(StrEnum):
    SEND = "send"
    WAIT = "wait"


async def _message(held: ScheduledSend) -> Message | None:
    async with get_sessionmaker()() as session:
        return await session.get(Message, held.message_id)


async def _they_replied(held: ScheduledSend, message: Message) -> bool:
    """A message arrived in the thread after the reply was scheduled."""
    if not message.thread_id:
        return False
    newer = select(Message.id).where(
        Message.thread_id == message.thread_id,
        Scope(owner_id=message.user_id).where(Message.user_id),
        Message.id != message.id,
        Message.created_at > held.created_at,
    )
    async with get_sessionmaker()() as session:
        return bool(await session.scalar(select(exists(newer))))


async def _you_replied(held: ScheduledSend, message: Message) -> bool | None:
    """The owner answered the thread after scheduling, from Gmail or anywhere: the listener never
    sees their own sent mail, so Gmail is asked. None when Gmail could not be reached."""
    if not message.thread_id:
        return False
    try:
        return await sent_message_in_thread_since(message.thread_id, held.created_at,
                                                  owner_id=message.user_id) is not None
    except (httpx.HTTPError, GmailAccessError, KeyError, ValueError) as exc:
        logger.warning("scheduled send %s: Gmail check failed, retrying next pass: %s", held.id, exc)
        return None


async def _verdict(held: ScheduledSend, now: datetime) -> CancelReason | Verdict:
    """Call it off with a reason, send it, or wait for the next pass (Gmail unreachable)."""
    if now > held.send_at + LATE_LIMIT:
        return CancelReason.TOO_LATE
    message = await _message(held)
    if message is None:
        return CancelReason.REFUSED
    if await _they_replied(held, message):
        return CancelReason.THEY_REPLIED
    you_replied = await _you_replied(held, message)
    if you_replied is None:
        return Verdict.WAIT
    return CancelReason.YOU_REPLIED if you_replied else Verdict.SEND


async def _call_off(schedule_id: UUID, user_id: UUID | None, message_id: UUID, reason: CancelReason) -> None:
    await audit(AuditAction.SCHEDULED_SEND_CANCELLED, user_id=user_id, message=message_id, reason=reason)
    logger.info("scheduled send %s cancelled: %s", schedule_id, reason)


async def _send(held: ScheduledSend) -> bool:
    """True once sent. A send that may have gone out keeps its claim; a refused one is called off."""
    try:
        email = await approve_and_send(str(held.message_id), held.draft, scope=Scope(owner_id=held.user_id))
    except SendOutcomeUnknownError:
        return False  # the message is marked for the reconciler; sending again risks a second copy
    except SendError as exc:
        await release(held.id)  # Gmail never took it: tried again next pass, until it is too late
        logger.warning("scheduled send %s failed, retrying: %s", held.id, exc)
        return False
    except DomainError as exc:
        if exc.code == ErrorCode.SEND_IN_PROGRESS:
            await release(held.id)
            return False
        await cancel_claimed(held.id, CancelReason.REFUSED)
        await _call_off(held.id, held.user_id, held.message_id, CancelReason.REFUSED)
        return False
    if email is None:  # the email is gone
        await cancel_claimed(held.id, CancelReason.REFUSED)
        return False
    return True


async def send_due() -> int:
    now = datetime.now(timezone.utc)
    sent = 0
    for held in await due(now):
        verdict = await _verdict(held, now)
        if verdict == Verdict.WAIT:
            continue
        if verdict != Verdict.SEND:
            await cancel(held.id, verdict)
            await _call_off(held.id, held.user_id, held.message_id, verdict)
            continue
        if await claim(held.id):
            sent += await _send(held)
    return sent
