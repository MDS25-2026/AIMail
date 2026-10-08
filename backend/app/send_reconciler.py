"""Settling sends whose outcome was lost (2026-10-08 audit).

A send whose answer from Gmail was lost keeps its claim, so it is never sent twice, and is marked unknown.
This job asks Gmail about marked sends only: if the owner's message is in the thread, the send is recorded as
done; if not, the claim is released so the reply can be sent again. An unmarked sent row is never touched:
the first version reconciled every sent row without a message id and released nine old replies that had
gone out (restored from Gmail, 2026-10-08).
"""

import logging
from collections.abc import Awaitable
from datetime import datetime, timedelta
from uuid import UUID

import httpx
from sqlalchemy import Select, func, select, update

from app import gmail_send
from app.audit import AuditAction, audit
from app.db.models import HoldingReply, Message
from app.db.session import get_sessionmaker

logger = logging.getLogger(__name__)

# Long enough for Gmail to show a message it accepted; short enough that a user can soon retry.
UNCONFIRMED_AFTER = timedelta(minutes=10)
# The claim is set just before the request; Gmail's timestamp can be a little earlier than ours.
CLOCK_SLACK = timedelta(minutes=2)
BATCH = 20
SENT = "sent"
NOT_SENT = "not_sent"


async def _ask_gmail(thread_id: str, claimed_at: datetime, owner_id: UUID | None) -> str | None:
    return await gmail_send.sent_message_in_thread_since(thread_id, claimed_at - CLOCK_SLACK, owner_id=owner_id)


def _settled(found: str | None) -> dict:
    """Done with Gmail's id, or released to be sent again; either way no longer unknown."""
    return {"sent_message_id": found, "send_outcome_unknown_at": None} if found else {
        "sent_at": None, "send_outcome_unknown_at": None}


async def mark_outcome_unknown(table: type[Message] | type[HoldingReply], row_id: UUID) -> None:
    async with get_sessionmaker()() as session, session.begin():
        await session.execute(update(table).where(table.id == row_id).values(send_outcome_unknown_at=func.now()))


async def _settle_reply(message: Message) -> None:
    found = await _ask_gmail(message.thread_id, message.sent_at, message.user_id)
    async with get_sessionmaker()() as session, session.begin():
        await session.execute(update(Message).where(Message.id == message.id, Message.sent_message_id.is_(None),
                                                    Message.send_outcome_unknown_at.is_not(None))
                              .values(**_settled(found)))
    await audit(AuditAction.SEND_RECONCILED, user_id=message.user_id, message=message.id,
                outcome=SENT if found else NOT_SENT)


async def _settle_holding_reply(reply: HoldingReply, thread_id: str) -> None:
    found = await _ask_gmail(thread_id, reply.sent_at, reply.user_id)
    async with get_sessionmaker()() as session, session.begin():
        await session.execute(update(HoldingReply)
                              .where(HoldingReply.id == reply.id, HoldingReply.sent_message_id.is_(None),
                                     HoldingReply.send_outcome_unknown_at.is_not(None))
                              .values(**_settled(found)))
    await audit(AuditAction.SEND_RECONCILED, user_id=reply.user_id, reply=reply.id,
                outcome=SENT if found else NOT_SENT)


def _unknown_replies() -> Select:
    """Only sends the send path marked unknown: an old sent row with no message id stays sent."""
    return select(Message).where(Message.send_outcome_unknown_at < func.now() - UNCONFIRMED_AFTER,
                                 Message.sent_message_id.is_(None), Message.thread_id.is_not(None)).limit(BATCH)


def _unknown_holding_replies() -> Select:
    return (select(HoldingReply, Message.thread_id).join(Message, Message.id == HoldingReply.message_id)
            .where(HoldingReply.send_outcome_unknown_at < func.now() - UNCONFIRMED_AFTER,
                   HoldingReply.sent_message_id.is_(None), Message.thread_id.is_not(None)).limit(BATCH))


async def _unconfirmed() -> tuple[list[Message], list[tuple[HoldingReply, str]]]:
    async with get_sessionmaker()() as session:
        replies = (await session.scalars(_unknown_replies())).all()
        holding = (await session.execute(_unknown_holding_replies())).all()
    return list(replies), [(reply, thread_id) for reply, thread_id in holding]


async def reconcile_sends() -> int:
    """Sends settled; one Gmail failure skips that row until the next pass."""
    replies, holding = await _unconfirmed()
    settled = 0
    for message in replies:
        settled += await _guarded(_settle_reply(message), message.id)
    for reply, thread_id in holding:
        settled += await _guarded(_settle_holding_reply(reply, thread_id), reply.id)
    return settled


async def _guarded(settle: Awaitable[None], row_id: UUID) -> int:
    try:
        await settle
    except (httpx.HTTPError, gmail_send.GmailAccessError) as exc:
        logger.warning("could not settle send %s yet: %s", row_id, exc)
        return 0
    return 1
