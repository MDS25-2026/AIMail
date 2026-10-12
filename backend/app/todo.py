"""To-do: what needs the reader (specs/features/todo-page.md).

Four lists: drafts the AI is unsure of, emails asking something of them, replies of theirs still
waiting for an answer, and drafts left unsent for over a day. An email is in one list only. Each shows the newest SECTION_LIMIT,
with its full count; "No reply needed" and "Not waiting" take an item out.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from sqlalchemy import ColumnElement, and_, case, func, or_, select, update
from sqlalchemy.dialects.postgresql import distinct_on, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import DashboardEmail
from app.core.ownership import Scope
from app.dashboard import inbox_row, thread_rows
from app.db.models import (
    AuthStatus,
    MaskingStatus,
    Message,
    SentMessage,
    UserPreferences,
)
from app.db.session import get_sessionmaker
from app.personalisation import Policy, load_policy
from app.quiet_hours import QuietHoursView, company_default, settings_for
from app.waiting import asks_something, working_days_since

SECTION_LIMIT = 50
DRAFT_REMINDER_AFTER = timedelta(hours=24)
DEFAULT_WAITING_DAYS = 3
# Most urgent first; within a priority, the longest waiting first.
PRIORITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


class TodoSection(BaseModel):
    emails: list[DashboardEmail]
    total: int


class WaitingReply(BaseModel):
    id: str
    subject: str
    sentAt: str
    threadId: str
    workingDays: int
    # The email in AIMail this reply answered, when there is one, to open it.
    email: DashboardEmail | None
    # Sent through AIMail, so AIMail can draft and send its follow-up; one sent from Gmail opens in Gmail.
    canFollowUp: bool


class Todo(BaseModel):
    needsAction: TodoSection
    needsReview: TodoSection
    unsentDrafts: TodoSection
    waiting: list[WaitingReply]
    waitingDays: int
    count: int
    # Sent, dismissed, not waited on or followed up since midnight in the reader's time zone.
    doneToday: int = 0


def _open(scope: Scope) -> list[ColumnElement[bool]]:
    """Unsent, readable, not dismissed, not a spoof and written by a person: what can still be acted on."""
    # Newsletters and notifications filled the lists with "no reply needed" rows (test run T19).
    return [scope.where(Message.user_id), Message.sent_at.is_(None), Message.dismissed_at.is_(None),
            Message.masking_status == MaskingStatus.COMPLETE,
            Message.auth_status.is_distinct_from(AuthStatus.SPOOF_DETECTED), Message.is_automated.is_(False),
            # Remind me later: back on the list when the snooze is due.
            or_(Message.snoozed_until.is_(None), Message.snoozed_until <= func.now())]


def _action_count() -> ColumnElement[int]:
    """How many action items, 0 for none or for a value that is not a list."""
    is_list = func.jsonb_typeof(Message.action_items) == "array"
    return case((is_list, func.jsonb_array_length(Message.action_items)), else_=0)


def _has_draft() -> ColumnElement[bool]:
    return func.coalesce(Message.draft_reply, "") != ""


def _sections() -> dict[str, list[ColumnElement[bool]]]:
    """Each email in one list only, the most urgent: review, then action, then an unsent draft."""
    is_review = and_(Message.needs_human_review.is_(True), _has_draft())
    is_action = _action_count() > 0
    is_stale_draft = and_(_has_draft(), Message.generated_at < func.now() - DRAFT_REMINDER_AFTER)
    return {
        "needsReview": [is_review],
        "needsAction": [is_action, ~is_review],
        "unsentDrafts": [is_stale_draft, ~is_review, ~is_action],
    }


async def _section_rows(session: AsyncSession, scope: Scope, conditions: list) -> tuple[list[Message], int]:
    where = [*_open(scope), *conditions]
    rows = (await session.scalars(select(Message).where(*where).order_by(Message.created_at.desc())
                                  .limit(SECTION_LIMIT))).all()
    total = await session.scalar(select(func.count()).select_from(Message).where(*where))
    return list(rows), total or 0


async def _sections_with_rows(session: AsyncSession, scope: Scope, policy: Policy) -> dict[str, TodoSection]:
    """All three lists' rows built together: one thread query and one name lookup between them."""
    found = {name: await _section_rows(session, scope, conditions) for name, conditions in _sections().items()}
    rows = await thread_rows(session, [message for messages, _ in found.values() for message in messages], policy)
    by_id = {row.id: row for row in rows}
    return {name: TodoSection(emails=by_urgency([by_id[str(m.id)] for m in messages]), total=total)
            for name, (messages, total) in found.items()}


def by_urgency(emails: list[DashboardEmail]) -> list[DashboardEmail]:
    return sorted(emails, key=lambda email: (PRIORITY_RANK[email.priority], email.timestamp))


async def _latest_inbound(session: AsyncSession, scope: Scope, thread_ids: list[str]) -> dict[str, Message]:
    """The newest received email in each thread."""
    if not thread_ids:
        return {}
    rows = (await session.scalars(
        select(Message).where(scope.where(Message.user_id), Message.thread_id.in_(thread_ids))
        .ext(distinct_on(Message.thread_id)).order_by(Message.thread_id, Message.created_at.desc()))).all()
    return {message.thread_id: message for message in rows}


async def _waiting(session: AsyncSession, scope: Scope, waiting_days: int, quiet: QuietHoursView,
                   policy: Policy) -> list[WaitingReply]:
    """The latest reply in each thread that asked something, has had no answer, and is overdue."""
    latest = (await session.scalars(
        select(SentMessage).where(scope.where(SentMessage.user_id), SentMessage.thread_id.is_not(None))
        .ext(distinct_on(SentMessage.thread_id)).order_by(SentMessage.thread_id, SentMessage.sent_at.desc()))).all()
    inbound = await _latest_inbound(session, scope, [sent.thread_id for sent in latest])
    now = datetime.now(timezone.utc)
    waiting = []
    for sent in latest:
        received = inbound.get(sent.thread_id)
        is_answered = received is not None and received.created_at > sent.sent_at
        is_tracked = sent.remind or asks_something(sent.body_masked)
        if sent.dismissed_at or is_answered or not is_tracked:
            continue
        days = working_days_since(sent.sent_at, now, quiet.weekendDays, quiet.timezone)
        if days < waiting_days:
            continue
        waiting.append(WaitingReply(id=str(sent.id), subject=sent.subject, sentAt=sent.sent_at.isoformat(),
                                    threadId=sent.thread_id, workingDays=days,
                                    email=inbox_row(received, policy) if received else None,
                                    canFollowUp=sent.message_id is not None))
    return sorted(waiting, key=lambda reply: reply.sentAt)[:SECTION_LIMIT]


async def _waiting_days(session: AsyncSession, user_id: UUID | None) -> int:
    if user_id is None:
        return DEFAULT_WAITING_DAYS
    days = await session.scalar(select(UserPreferences.waiting_days).where(UserPreferences.user_id == user_id))
    return days or DEFAULT_WAITING_DAYS


def _start_of_today(timezone_name: str) -> datetime:
    now = datetime.now(ZoneInfo(timezone_name))
    return now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


async def _done_since(session: AsyncSession, scope: Scope, since: datetime) -> int:
    """From live columns, not the audit log, so an undone dismissal no longer counts."""
    emails = await session.scalar(select(func.count()).select_from(Message).where(
        scope.where(Message.user_id), or_(Message.sent_at >= since, Message.dismissed_at >= since)))
    replies = await session.scalar(select(func.count()).select_from(SentMessage).where(
        scope.where(SentMessage.user_id), or_(SentMessage.dismissed_at >= since, SentMessage.followed_up_at >= since)))
    return (emails or 0) + (replies or 0)


async def todo_for(scope: Scope, policy_email: str) -> Todo:
    quiet = (await settings_for(scope.owner_id)).effective if scope.owner_id else await company_default()
    async with get_sessionmaker()() as session:
        policy = await load_policy(session, policy_email)
        sections = await _sections_with_rows(session, scope, policy)
        waiting_days = await _waiting_days(session, scope.owner_id)
        waiting = await _waiting(session, scope, waiting_days, quiet, policy)
        done_today = await _done_since(session, scope, _start_of_today(quiet.timezone))
    # The lists never share an email, so their totals add up to distinct emails.
    count = sum(section.total for section in sections.values()) + len(waiting)
    return Todo(**sections, waiting=waiting, waitingDays=waiting_days, count=count, doneToday=done_today)


async def dismiss_email(scope: Scope, message_id: UUID, is_dismissed: bool) -> bool:
    """No reply needed: out of the to-do lists; the email stays in the inbox."""
    async with get_sessionmaker()() as session, session.begin():
        changed = await session.scalar(
            update(Message).where(Message.id == message_id, scope.where(Message.user_id))
            .values(dismissed_at=func.now() if is_dismissed else None).returning(Message.id))
    return changed is not None


async def dismiss_waiting(scope: Scope, sent_id: UUID, is_dismissed: bool) -> bool:
    """Not waiting: this reply leaves the waiting list; undone, it comes back."""
    async with get_sessionmaker()() as session, session.begin():
        changed = await session.scalar(
            update(SentMessage).where(SentMessage.id == sent_id, scope.where(SentMessage.user_id))
            .values(dismissed_at=func.now() if is_dismissed else None).returning(SentMessage.id))
    return changed is not None


async def save_waiting_days(user_id: UUID, days: int) -> None:
    async with get_sessionmaker()() as session, session.begin():
        await session.execute(insert(UserPreferences).values(user_id=user_id, waiting_days=days)
                              .on_conflict_do_update(index_elements=["user_id"], set_={"waiting_days": days}))
