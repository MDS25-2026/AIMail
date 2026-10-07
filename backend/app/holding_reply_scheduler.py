"""Schedules, re-checks and sends holding replies (specs/features/holding-reply.md).

Every poll: emails that qualify on arrival get a reply scheduled for HOLD_WINDOW later. When it is
due, every condition is checked again against the current settings and Gmail (the user may have
answered meanwhile, in AIMail or in Gmail itself), and the reply is sent or cancelled with the
reason. A reply that cannot be sent in time is cancelled rather than sent late.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from uuid import UUID

import httpx
from sqlalchemy import exists, func, select, update
from sqlalchemy.dialects.postgresql import insert

from app import gmail_send
from app.audit import audit
from app.core.constants import (
    HOLD_WINDOW_MINUTES,
    HOLDING_REPLY_DAILY_CAP,
    HOLDING_REPLY_POLL_SECONDS,
    HOLDING_REPLY_STALE_MINUTES,
)
from app.core.language import Language, detect_language
from app.db.models import HoldingReply, HoldingReplySettings, Message, UserProfile
from app.db.session import get_sessionmaker
from app.holding_reply import (
    Audience,
    Refusal,
    ReplyScope,
    address_of,
    choose_language,
    refusal_on_arrival,
    render,
)

logger = logging.getLogger(__name__)

HOLD_WINDOW = timedelta(minutes=HOLD_WINDOW_MINUTES)
STALE_AFTER = timedelta(minutes=HOLDING_REPLY_STALE_MINUTES)
# Marks the reply as automatic, so a compliant auto-responder does not answer it back (RFC 3834).
AUTO_REPLY_HEADERS = {"Auto-Submitted": "auto-replied", "X-Auto-Response-Suppress": "All"}


class Verdict(StrEnum):
    SEND = "send"
    # Not decidable yet (drafting unfinished, Gmail unreachable): look again next poll.
    WAIT = "wait"


@dataclass(frozen=True)
class Due:
    reply: HoldingReply
    message: Message
    settings: HoldingReplySettings
    owner_email: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def schedule_new() -> int:
    """Schedule a reply for each recent email that qualifies on arrival."""
    now = _now()
    stmt = (
        select(Message, HoldingReplySettings, UserProfile.email)
        .join(HoldingReplySettings, HoldingReplySettings.user_id == Message.user_id)
        .join(UserProfile, UserProfile.id == Message.user_id)
        .where(HoldingReplySettings.enabled, Message.received_at >= HoldingReplySettings.enabled_at,
               Message.received_at >= now - HOLD_WINDOW - STALE_AFTER,
               ~exists(select(HoldingReply.id).where(HoldingReply.message_id == Message.id)))
    )
    scheduled = 0
    async with get_sessionmaker()() as session, session.begin():
        for message, settings, owner_email in (await session.execute(stmt)).all():
            if refusal_on_arrival(message, settings, owner_email):
                continue
            language = choose_language(detect_language(message.body_masked or ""), settings)
            await session.execute(insert(HoldingReply).values(
                user_id=message.user_id, message_id=message.id, language=language,
                recipient_addr=address_of(message.from_addr),
                scheduled_for=(message.received_at or now) + HOLD_WINDOW,
            ).on_conflict_do_nothing(index_elements=["message_id"]))
            scheduled += 1
    if scheduled:
        await audit("holding_reply_scheduled", f"count={scheduled}")
    return scheduled


async def _count(stmt) -> int:
    async with get_sessionmaker()() as session:
        return await session.scalar(stmt) or 0


async def _store_refusal(due: Due, now: datetime) -> Refusal | None:
    """The database-side conditions at send time."""
    user_id, recipient = due.reply.user_id, due.reply.recipient_addr
    sent_today = await _count(select(func.count()).select_from(HoldingReply).where(
        HoldingReply.user_id == user_id, HoldingReply.sent_at >= now - timedelta(days=1)))
    recent_to_sender = await _count(select(func.count()).select_from(HoldingReply).where(
        HoldingReply.user_id == user_id, HoldingReply.recipient_addr == recipient,
        HoldingReply.sent_at >= now - timedelta(days=due.settings.cooldown_days)))
    checks = (
        (due.message.sent_at is not None, Refusal.USER_REPLIED),
        (sent_today >= HOLDING_REPLY_DAILY_CAP, Refusal.DAILY_CAP),
        (recent_to_sender > 0, Refusal.COOLDOWN),
        (due.settings.scope == ReplyScope.NEEDS_REPLY and due.message.generated_at is not None
         and not due.message.draft_reply, Refusal.NO_REPLY_NEEDED),
        (not due.message.thread_id, Refusal.NO_THREAD),
    )
    return next((refusal for is_refused, refusal in checks if is_refused), None)


async def _gmail_refusal(due: Due) -> Refusal | None:
    """The Gmail-side conditions: did the user answer from anywhere, and do they know the sender."""
    owner_id = due.reply.user_id
    received = due.message.received_at or due.message.created_at
    if await gmail_send.replied_in_thread_since(due.message.thread_id, received, owner_id=owner_id):
        return Refusal.USER_REPLIED
    is_correspondent = due.settings.audience != Audience.CORRESPONDENTS or await gmail_send.has_written_to(
        due.reply.recipient_addr, owner_id=owner_id)
    return None if is_correspondent else Refusal.NOT_CORRESPONDENT


async def verdict_when_due(due: Due, now: datetime) -> Refusal | Verdict:
    """Every condition again, against current settings: a refusal, send, or wait and look again."""
    if now > due.reply.scheduled_for + STALE_AFTER:
        return Refusal.STALE
    refusal = refusal_on_arrival(due.message, due.settings, due.owner_email) or await _store_refusal(due, now)
    if refusal:
        return refusal
    if due.settings.scope == ReplyScope.NEEDS_REPLY and due.message.generated_at is None:
        return Verdict.WAIT  # the router has not judged it yet
    try:
        return await _gmail_refusal(due) or Verdict.SEND
    except (httpx.HTTPError, gmail_send.GmailAccessError, KeyError, ValueError) as exc:
        logger.warning("holding reply %s: Gmail check failed, retrying next poll: %s", due.reply.id, exc)
        return Verdict.WAIT


async def _cancel(reply_id: UUID, reason: Refusal, owner_id: UUID | None) -> None:
    async with get_sessionmaker()() as session, session.begin():
        await session.execute(update(HoldingReply).where(
            HoldingReply.id == reply_id, HoldingReply.sent_at.is_(None),
            HoldingReply.cancelled_reason.is_(None)).values(cancelled_reason=reason))
    await audit("holding_reply_cancelled", f"reply={reply_id} reason={reason}", user_id=owner_id)


async def _claim(reply_id: UUID) -> bool:
    """Claim-then-send, as approve_and_send does: two backends can never both send it."""
    async with get_sessionmaker()() as session, session.begin():
        claimed = await session.scalar(update(HoldingReply).where(
            HoldingReply.id == reply_id, HoldingReply.sent_at.is_(None),
            HoldingReply.cancelled_reason.is_(None)).values(sent_at=func.now()).returning(HoldingReply.id))
    return claimed is not None


async def _release(reply_id: UUID) -> None:
    async with get_sessionmaker()() as session, session.begin():
        await session.execute(update(HoldingReply).where(HoldingReply.id == reply_id).values(sent_at=None))


async def _send(due: Due) -> None:
    language = Language(due.reply.language)
    text = render(due.settings.templates[language], language, due.message.from_addr, due.settings.leave_until)
    if not await _claim(due.reply.id):
        return
    try:
        sent = await gmail_send.send_reply(
            due.message.gmail_message_id, due.message.from_addr or "", due.message.subject or "", text,
            owner_id=due.reply.user_id, extra_headers=AUTO_REPLY_HEADERS)
    except gmail_send.SendOutcomeUnknownError:
        await audit("holding_reply_outcome_unknown", f"reply={due.reply.id}", success=False,
                    user_id=due.reply.user_id)
        return  # the claim stays: Gmail may have sent it, and a second copy is worse than none
    except gmail_send.SendError as exc:
        await _release(due.reply.id)
        logger.warning("holding reply %s not sent, retrying next poll: %s", due.reply.id, exc)
        return
    async with get_sessionmaker()() as session, session.begin():
        await session.execute(update(HoldingReply).where(HoldingReply.id == due.reply.id)
                              .values(sent_message_id=sent.message_id))
    await audit("holding_reply_sent", f"reply={due.reply.id} language={language}",
                user_id=due.reply.user_id)


async def send_due() -> int:
    now = _now()
    stmt = (
        select(HoldingReply, Message, HoldingReplySettings, UserProfile.email)
        .join(Message, Message.id == HoldingReply.message_id)
        .join(HoldingReplySettings, HoldingReplySettings.user_id == HoldingReply.user_id)
        .join(UserProfile, UserProfile.id == HoldingReply.user_id)
        .where(HoldingReply.sent_at.is_(None), HoldingReply.cancelled_reason.is_(None),
               HoldingReply.scheduled_for <= now)
    )
    async with get_sessionmaker()() as session:
        due_rows = [Due(*row) for row in (await session.execute(stmt)).all()]
    sent = 0
    for due in due_rows:
        verdict = await verdict_when_due(due, now)
        if verdict == Verdict.WAIT:
            continue  # stale replies come back as Refusal.STALE, so waiting always ends
        if verdict != Verdict.SEND:
            await _cancel(due.reply.id, verdict, due.reply.user_id)
            continue
        await _send(due)
        sent += 1
    return sent


async def holding_replies_loop() -> None:
    """Runs for the life of the process; a failed pass is logged and tried again next poll."""
    while True:
        try:
            await schedule_new()
            await send_due()
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("holding reply pass failed")
        await asyncio.sleep(HOLDING_REPLY_POLL_SECONDS)
