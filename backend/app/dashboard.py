"""Assembly of the dashboard email view (Lane D shape) from the `messages` table.

`list_dashboard_emails` is the fast list (Lane A fields + Lane B priority, no generation).
`email_detail` returns a single email with the Lane C generation. It generates once (retrieve
policy context via Lane B, call Lane C's /process-email) and caches the result on the row, so
reopening serves stored text instead of regenerating. Generation is best-effort: if Lane C is
unreachable the email still returns with its Lane A/B fields and stays uncached for a later retry.
"""

import logging
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr
from enum import Enum
from uuid import UUID
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel
from sqlalchemy import ColumnElement, Text, cast, func, or_, select, tuple_, update
from sqlalchemy.dialects.postgresql import distinct_on, insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app import agent_client, connections
from app.agent_contract import (
    MAX_TRANSLATE_CHARS,
    TONE_PROMPTS,
    ProcessEmailRequest,
    ProcessEmailResponse,
    RefineResponse,
    ReviewCode,
    Tone,
    TranslateRequest,
    TranslateResponse,
)
from app.agent_contract import RefineRequest as AgentRefineRequest
from app.attachment_notes import has_unread_attachment
from app.audit import AuditAction, audit, record
from app.contracts import (
    DashboardEmail,
    Detail,
    EmailPage,
    MeasureView,
    QuantityView,
    Source,
    ThreadMessage,
)
from app.core.config import get_settings
from app.core.constants import MAX_SCHEDULE_AHEAD_DAYS, TEMPLATE_TIMEZONE
from app.core.cursor import Cursor
from app.core.errors import DomainError, ErrorCode
from app.core.language import Language, detect_language
from app.core.ownership import EVERYTHING, Scope
from app.core.redaction import PLACEHOLDER, has_redaction_marker
from app.core.typed_names import TypedNames
from app.core.typed_text import mask_typed_text
from app.core.vault import ThreadMap, VaultUnavailableError, build_thread_map
from app.db.models import (
    AuthStatus,
    MaskingStatus,
    Message,
    ModelEgress,
    ReplyTemplate,
    SentMessage,
    UserProfile,
)
from app.db.session import get_sessionmaker
from app.draft_storage import egress_view as _egress_view
from app.draft_storage import rag_context_of
from app.draft_storage import review_columns as _review_fields
from app.draft_storage import source_records as _source_records
from app.egress_log import egress_for, save_egress
from app.email_policy import Action, refusal_for
from app.gmail_send import SendError, SendOutcomeUnknownError, SentReply, send_reply
from app.jobs import (
    claim_for_drafting,
    claim_requested,
    release_drafting,
    request_draft,
)
from app.ml.category import EmailCategory
from app.normalise.quantities import quantities_in
from app.owner import owner_name as _owner_name
from app.past_replies import remember_reply
from app.personalisation import (
    DEFAULT_POLICY,
    Policy,
    apply_policy,
    load_policy,
    load_policy_for_user,
)
from app.plain_text import plain_text
from app.private_mode import model_for
from app.rag.errors import EmbeddingError
from app.rag.mask import DocumentMaskingError
from app.rag.retrieve import retrieve
from app.rag.utils import format_rag_context
from app.retention import KEEP_FOREVER
from app.review_reasons import review_reasons
from app.scheduled_sends import (
    CancelReason,
    ScheduleState,
    cancel_pending,
    hold,
    states_for,
    waiting_send_exists,
)
from app.send_reconciler import mark_follow_up_unknown, mark_outcome_unknown
from app.template_store import suggested_template_id
from app.templates import (
    fill_variables,
    format_day,
    has_unfilled_variable,
    protect_variables,
    restore_variables,
)
from app.writing_style import edit_ratio, is_learning, relearn, style_for
from model_gateway import track_egress

logger = logging.getLogger(__name__)



def _quantity_views(text: str) -> list[QuantityView]:
    return [
        QuantityView(
            text=q.text, system=q.system,
            metric=MeasureView(value=q.metric.value, unit=q.metric.unit),
            imperial=MeasureView(value=q.imperial.value, unit=q.imperial.unit),
        )
        for q in quantities_in(text)
    ]


# The thread the model sees: the latest few earlier messages, each cut short. Enough to know what
# was already said; bounded so one long thread cannot crowd the email itself out of the prompt.
THREAD_CONTEXT_MESSAGES = 5
THREAD_CONTEXT_CHARS_EACH = 1500


async def _thread_of(session: AsyncSession, message: Message) -> list[Message]:
    """The other masked messages in this Gmail thread, oldest first."""
    if not message.thread_id:
        return []
    stmt = (
        select(Message)
        .where(
            Message.thread_id == message.thread_id,
            # Thread ids are per mailbox; never pull another owner's messages into a prompt.
            Scope(owner_id=message.user_id).where(Message.user_id),
            Message.id != message.id,
            Message.masking_status == MaskingStatus.COMPLETE,
        )
        .order_by(Message.received_at)
    )
    return list((await session.scalars(stmt)).all())


def thread_context(message: Message, thread: list[Message], details: ThreadMap | None = None) -> str:
    """Earlier messages for the model, labelled by position. Never by sender: from_addr is stored
    unmasked and is documented as never entering a model payload."""
    details = details or ThreadMap()
    before = [m for m in thread if m.received_at and message.received_at
              and m.received_at < message.received_at][-THREAD_CONTEXT_MESSAGES:]
    return "\n\n".join(_context_entry(index, m, details) for index, m in enumerate(before, 1))


def _context_entry(index: int, earlier: Message, details: ThreadMap) -> str:
    # plain_text first: many stored bodies are HTML (#108), and cutting markup first would hand
    # the model 1500 characters of <style> instead of what was said.
    body = details.renumber(str(earlier.id), plain_text(earlier.body_masked or ""))
    entry = f"Earlier message {index}:\n{body[:THREAD_CONTEXT_CHARS_EACH]}"
    if not _sent_reply(earlier):
        return entry
    # The owner typed this reply: known details go back to placeholders, new formats are masked.
    reply = details.for_model(plain_text(earlier.draft_reply or ""))[:THREAD_CONTEXT_CHARS_EACH]
    return f"{entry}\n\nYour reply to earlier message {index}:\n{reply}"


def _sent_reply(message: Message) -> bool:
    return message.sent_at is not None and bool(message.draft_reply)


THREAD_SNIPPET_CHARS = 200


def _thread_view(thread: list[Message], details: ThreadMap, sent: list[SentMessage] | None = None) -> list[ThreadMessage]:
    """Each message in the thread in time order, with the owner's replies: those sent from AIMail right
    under the one they answered, and those sent from Gmail itself where they fall in time."""
    view: list[ThreadMessage] = []
    for m in thread:
        key = str(m.id)
        received = m.received_at or m.created_at
        view.append(ThreadMessage(
            sender=m.from_addr or "", snippet=details.renumber(key, m.snippet_masked or ""),
            body=details.renumber(key, m.body_masked or ""),
            timestamp=received.isoformat() if received else None,
        ))
        if _sent_reply(m):
            reply = m.draft_reply or ""
            view.append(ThreadMessage(
                sender="", snippet=plain_text(reply)[:THREAD_SNIPPET_CHARS], isOwnReply=True, body=reply,
                timestamp=m.sent_at.isoformat(),
            ))
    for reply in sent or []:
        body = details.renumber(_sent_key(reply), reply.body_masked or "")
        view.append(ThreadMessage(sender="", snippet=plain_text(body)[:THREAD_SNIPPET_CHARS], isOwnReply=True,
                                  body=body, timestamp=reply.sent_at.isoformat()))
    # Stable, so a reply sent from AIMail stays right under the message it answered.
    return sorted(view, key=lambda entry: entry.timestamp or "")


def _sent_key(reply: SentMessage) -> str:
    return f"sent:{reply.id}"


async def _gmail_replies(message: Message, session: AsyncSession | None = None) -> list[SentMessage]:
    """The owner's replies in this thread sent from Gmail itself; AIMail's own sends are on the message."""
    if not message.thread_id:
        return []
    async with nullcontext(session) if session is not None else get_sessionmaker()() as active:
        return list((await active.scalars(select(SentMessage).where(
            SentMessage.thread_id == message.thread_id, Scope(owner_id=message.user_id).where(SentMessage.user_id),
            SentMessage.message_id.is_(None)).order_by(SentMessage.sent_at))).all())


def is_drafting(message: Message) -> bool:
    """A first draft is on its way: none yet, not sent, allowed, and not already tried and failed."""
    return (message.generated_at is None and message.sent_at is None and not refusal_for(message, Action.DRAFT)
            and not message.generation_attempts)


async def _policy_for(message: Message, session: AsyncSession | None = None) -> Policy:
    """The owner's priority rules, as the inbox list applies them, so a priority never changes on opening."""
    if message.user_id is None:
        return DEFAULT_POLICY  # a row with no owner, seen only by a script, as the list shows it
    async with nullcontext(session) if session is not None else get_sessionmaker()() as active:
        return await load_policy_for_user(active, message.user_id)


def _to_email(
    message: Message,
    policy: Policy = DEFAULT_POLICY,
    thread: list[Message] | None = None,
    details: ThreadMap | None = None,
    egress: list[ModelEgress] | None = None,
    schedule: ScheduleState | None = None,
    sent: list[SentMessage] | None = None,
    has_unread_attachment: bool = False,
) -> DashboardEmail:
    details = details or ThreadMap()
    # Their placeholders have no stored values: appended after the thread's, so they take new numbers
    # with none, never another person's (and the numbers drafts already use stay as they are).
    for reply in sent or []:
        details.add_message(_sent_key(reply), None, reply.body_masked or "")
    schedule = schedule or ScheduleState()
    key = str(message.id)
    return DashboardEmail(
        id=key,
        sender=message.from_addr or "",
        subject=details.renumber(key, message.subject or ""),
        preview=details.renumber(key, message.snippet_masked or ""),
        body=details.renumber(key, message.body_masked or ""),
        timestamp=(message.received_at or message.created_at).isoformat(),
        authStatus=AuthStatus(message.auth_status or AuthStatus.UNVERIFIED),
        # The classifier's prediction, then the user's policy on top of it.
        priority=apply_policy(message, policy),
        # Stored by the worker (app/ml/categorise.py); never predicted while the inbox loads.
        category=message.category or EmailCategory.INTERNAL,
        categoryConfidence=message.category_confidence,
        threadContext=_thread_view(thread or [], details, sent),
        aiSummary=message.ai_summary or "",
        actionItems=message.action_items or [],
        draftReply=message.draft_reply or "",
        tone=Tone(message.draft_tone or Tone.PROFESSIONAL),
        isDrafting=is_drafting(message),
        sources=[Source(**source) for source in message.rag_sources or []],
        piiMasked=bool((message.emails_masked or 0) + (message.phones_masked or 0)),
        criticConfidence=message.critic_confidence or 0.0,
        reviewReasons=review_reasons(message.critic_checks),
        sentAt=message.sent_at.isoformat() if message.sent_at else None,
        isRead=message.read_at is not None,
        quantities=_quantity_views(message.body_masked or ""),
        masking=message.masking_status or MaskingStatus.COMPLETE,
        replyTo=message.reply_to or None,
        threadId=message.thread_id,
        details=[Detail(**detail) for detail in details.details()],
        egress=[_egress_view(row) for row in egress or []],
        senderUtcOffsetMinutes=_sender_offset(message),
        isAutomated=bool(message.is_automated),
        hasUnreadAttachment=has_unread_attachment,
        scheduledFor=schedule.send_at.isoformat() if schedule.send_at else None,
        scheduleCancelled=schedule.cancelled,
        snoozedUntil=message.snoozed_until.isoformat() if message.snoozed_until else None,
    )


# +0000 is what mail servers stamp, not where a person is; an automated sender is no person at all.
UTC_STAMP_MINUTES = 0


def _sender_offset(message: Message) -> int | None:
    """The sender's UTC offset, or None when it says nothing about where a person is."""
    offset = message.sender_utc_offset_minutes
    if message.is_automated or offset == UTC_STAMP_MINUTES:
        return None
    return offset


async def _details_for(message: Message, thread: list[Message], session: AsyncSession | None = None) -> ThreadMap:
    """The conversation's placeholders and their values, oldest message first, plus the owner's
    name as the sign-off placeholder. Opened per request and never stored or logged."""
    return _thread_map(message, thread, await _owner_name(message.user_id, session))


def _thread_map(message: Message, thread: list[Message], owner_name: str) -> ThreadMap:
    ordered = sorted([*thread, message], key=lambda m: m.received_at or m.created_at or datetime.min.replace(tzinfo=timezone.utc))
    return build_thread_map(
        [(str(m.id), m.pii_vault, m.user_id, m.gmail_message_id or "",
          f"{m.subject or ''}\n{m.snippet_masked or ''}\n{m.body_masked or ''}") for m in ordered],
        owner_name,
        parseaddr(message.from_addr or "")[0],
    )


def thread_row(message: Message, thread: list[Message], owner_name: str, policy: Policy) -> DashboardEmail:
    """A row whose action items, summary and draft can be shown: the AI wrote them in the thread's numbering."""
    return _to_email(message, policy, details=_thread_map(message, thread, owner_name))


async def thread_rows(session: AsyncSession, messages: list[Message], policy: Policy) -> list[DashboardEmail]:
    """thread_row for many emails, with one query for all their threads and one name per owner."""
    thread_ids = {m.thread_id for m in messages if m.thread_id}
    others = (await session.scalars(select(Message).where(
        Message.thread_id.in_(thread_ids), Message.user_id.in_({m.user_id for m in messages}),
        Message.masking_status == MaskingStatus.COMPLETE))).all() if thread_ids else []
    by_thread: dict[tuple[UUID | None, str], list[Message]] = {}
    for other in others:
        by_thread.setdefault((other.user_id, other.thread_id), []).append(other)
    owners = {m.user_id for m in messages if m.user_id}
    owner_names = dict((await session.execute(select(UserProfile.id, UserProfile.display_name)
                                              .where(UserProfile.id.in_(owners)))).tuples().all()) if owners else {}
    return [thread_row(m, [o for o in by_thread.get((m.user_id, m.thread_id), []) if o.id != m.id],
                       owner_names.get(m.user_id) or "", policy) for m in messages]


async def _thread_for(message: Message) -> list[Message]:
    if not message.thread_id:
        return []
    async with get_sessionmaker()() as session:
        return await _thread_of(session, message)


def _thread_key() -> ColumnElement[str]:
    """A thread's identity; an email with no thread is a thread of its own."""
    return func.coalesce(Message.thread_id, cast(Message.id, Text))


async def list_dashboard_emails(scope: Scope, policy_email: str, limit: int, after: Cursor | None) -> EmailPage:
    """One page of whole conversations, newest first (specs/features/inbox-threads.md). A thread is placed
    by its newest email and comes with every visible email in it, so it never splits across pages; the
    browser groups each into one row."""
    # A snoozed email stays out of the inbox until it is due, unless a reply to it is waiting to go
    # out: the Scheduled page reads this list, and it must always reach the Cancel button.
    visible = [scope.where(Message.user_id), or_(
        Message.snoozed_until.is_(None), Message.snoozed_until <= func.now(), waiting_send_exists(Message.id))]
    newest = (select(Message.id, Message.created_at, _thread_key().label("key")).where(*visible)
              .ext(distinct_on(_thread_key())).order_by(_thread_key(), Message.created_at.desc(), Message.id.desc())
              .subquery())
    heads = select(newest.c.key, newest.c.created_at, newest.c.id)
    if after:
        heads = heads.where(tuple_(newest.c.created_at, newest.c.id) < (after.created_at, after.row_id))
    # One extra thread says whether another page exists without a count query; id breaks ties.
    heads = heads.order_by(newest.c.created_at.desc(), newest.c.id.desc()).limit(limit + 1)
    async with get_sessionmaker()() as session:
        found = (await session.execute(heads)).all()
        page = found[:limit]
        rows = (await session.scalars(select(Message).where(*visible, _thread_key().in_([h.key for h in page]))
                                      .order_by(Message.created_at.desc(), Message.id.desc()))).all() if page else []
        policy = await load_policy(session, policy_email)
        replied = await _latest_gmail_replies(session, scope, rows)
    schedules = await states_for([message.id for message in rows])
    emails = [inbox_row(message, policy, schedules.get(message.id), is_answered=_is_answered(message, replied))
              for message in rows]
    last = page[-1] if len(found) > limit else None
    return EmailPage(emails=emails, nextCursor=Cursor(last.created_at, last.id).encode() if last else None)


async def _latest_gmail_replies(session: AsyncSession, scope: Scope, rows: list[Message]) -> dict[str, datetime]:
    """When the reader last replied in each thread from Gmail itself."""
    thread_ids = {m.thread_id for m in rows if m.thread_id}
    if not thread_ids:
        return {}
    found = await session.execute(select(SentMessage.thread_id, func.max(SentMessage.sent_at))
                                  .where(scope.where(SentMessage.user_id), SentMessage.thread_id.in_(thread_ids))
                                  .group_by(SentMessage.thread_id))
    return dict(found.tuples().all())


def _is_answered(message: Message, latest_gmail_reply: dict[str, datetime]) -> bool:
    """Answered from AIMail, or a reply sent from Gmail in its thread after it arrived."""
    if message.sent_at is not None:
        return True
    replied = latest_gmail_reply.get(message.thread_id or "")
    arrived = message.received_at or message.created_at
    return replied is not None and arrived is not None and replied > arrived


def inbox_row(message: Message, policy: Policy, schedule: ScheduleState | None = None,
              is_answered: bool = False) -> DashboardEmail:
    """An email as a list shows it: its own subject and preview details, no thread or draft detail."""
    email = _to_email(message, policy, details=_own_details(message), schedule=schedule)
    return email.model_copy(update={"isAnswered": is_answered}) if is_answered else email


def _own_details(message: Message) -> ThreadMap:
    """One email's details in its own numbering, for its row's subject and preview. Not for the action
    items, summary or draft: the AI wrote those in the thread's numbering (thread_row)."""
    text = "\n".join([message.subject or "", message.snippet_masked or "", *(message.action_items or [])])
    return build_thread_map(
        [(str(message.id), message.pii_vault, message.user_id, message.gmail_message_id or "", text)], ""
    )




class AlreadySentError(DomainError):
    """The draft of a sent message is the record of what went out; it is never replaced."""

    def __init__(self, message_id: str = "") -> None:
        super().__init__(ErrorCode.ALREADY_SENT, f"message {message_id} was already sent")


class DraftNotUpdatedError(DomainError):
    """A regenerate or refine that changed nothing. Answering 200 with the old draft hid it."""


@dataclass(frozen=True)
class OutgoingReply:
    stored: str  # known details as placeholders: what the database keeps
    sent: str  # every placeholder filled in: what the recipient reads
    restored: int


def _outgoing(draft: str, details: ThreadMap) -> OutgoingReply:
    """The approved draft as stored and as sent. Raises SendRejectedError before anything is
    claimed if it would show the recipient a marker or a placeholder nobody can fill."""
    stored = details.tokenise_known(draft)
    sent, unresolved = details.restore(stored)
    if unresolved:
        raise SendRejectedError(ErrorCode.UNRESOLVED_PLACEHOLDERS)
    if has_redaction_marker(sent):
        raise SendRejectedError(ErrorCode.REDACTION_MARKERS)
    if has_unfilled_variable(sent):
        raise SendRejectedError(ErrorCode.UNRESOLVED_PLACEHOLDERS)  # a template's {{blank}} left in
    return OutgoingReply(stored=stored, sent=sent, restored=len(PLACEHOLDER.findall(stored)))


class SendRejectedError(DomainError):
    """A draft refused before anything is claimed or sent; the dashboard's own check can be bypassed."""


def _require(message: Message, action: Action) -> None:
    """Raise the action's own error type for whatever the email policy refuses."""
    code = refusal_for(message, action)
    if code is None:
        return
    if code == ErrorCode.ALREADY_SENT:
        raise AlreadySentError(str(message.id))
    raise _REFUSAL_ERROR[action](code)


class GenerationOutcome(Enum):
    STORED = "stored"  # a new draft is in place
    NO_REPLY = "no_reply"  # stored with no draft: routed NA, or refused with no draft to keep
    KEPT = "kept"  # refused for content; the reviewer's existing draft stays
    FAILED = "failed"  # the agent or retrieval failed; an attempt was counted
    SKIPPED = "skipped"  # quarantined, or sent while the draft was being written


async def generate_pending(limit: int | None = None) -> int:
    """Generate + cache drafts for messages without one; return how many were generated.

    Shared by the `make generate` script (no limit) and the background poller (small batch, to stay
    under Gemini's free-tier rate limit). Fewest attempts first, so a message that keeps failing
    sinks behind newer ones. No connection is held while the agent works.
    """
    return await _draft_claimed(await claim_for_drafting(limit))


async def generate_requested(limit: int) -> int:
    """Draft the emails people opened and are waiting on (request_draft); the worker runs this often."""
    return await _draft_claimed(await claim_requested(limit))


async def _draft_claimed(claimed: list[UUID]) -> int:
    generated = 0
    for pk in claimed:
        try:
            loaded = await _load_with_thread(pk, EVERYTHING)
            if loaded and await _generate_and_store(*loaded) is GenerationOutcome.STORED:
                generated += 1
        except (SQLAlchemyError, VaultUnavailableError):
            # One email's failure is logged and the rest of the batch still drafts; this one is retried later.
            logger.exception("drafting message %s failed; continuing with the batch", pk)
        finally:
            await release_drafting(pk)
    return generated


async def _load_with_thread(pk: UUID, scope: Scope) -> tuple[Message, list[Message]] | None:
    """The message and its thread, read in one short session that is closed before any agent call."""
    async with get_sessionmaker()() as session:
        message = await _get(session, pk, scope)
        if message is None:
            return None
        return message, await _thread_of(session, message)


async def _update_unsent(pk: UUID, fields: dict) -> bool:
    """Write only these columns, and only while the message is unsent.

    Never a whole-object save: a copy read before a slow agent call would write back a stale
    sent_at and undo a send that happened meanwhile.
    """
    async with get_sessionmaker()() as session:
        updated = await session.scalar(
            update(Message)
            .where(Message.id == pk, Message.sent_at.is_(None))
            .values(**fields)
            .returning(Message.id)
        )
        await session.commit()
    return updated is not None


async def _call_agent(path: str, request: BaseModel, answer: type[BaseModel]) -> dict:
    """The agent's validated answer (app/agent_client.py), as the dict the storing code reads."""
    return (await agent_client.call(path, request, answer)).model_dump()


# The agent's "this will fail the same way every time" status (cut off, blocked, rejected input).
AGENT_CONTENT_FAILURE = 422


NOT_DRAFTED = "not_drafted"


def _not_drafted(code: str) -> dict:
    """Stored like an NA route: a human handles it, and the poller stops retrying a failure that
    repeats at temperature 0 and would otherwise spend quota every cycle."""
    return {"category": "NA", "draft": None, "summary": "", "action_items": [],
            "needs_human_review": True, "review_reasons": [f"no draft: {code}"],
            "review_codes": [{"code": ReviewCode.NO_DRAFT, "items": []}], NOT_DRAFTED: True}


async def _generate(message: Message, tone: Tone, thread: list[Message], details: ThreadMap) -> dict:
    """Retrieve policy context (Lane B) and call Lane C's /process-email. Returns {} on any failure.

    The chunks ride along under "rag_sources" so the caller stores what the draft was grounded on.
    """
    searched: list[dict] = []
    refused: list[dict] = []
    try:
        provider = await model_for(message.user_id)
        with track_egress() as searched:
            chunks = await retrieve(message.body_masked or "", k=5, scope=Scope(owner_id=message.user_id),
                                    provider=provider)
        names = TypedNames()
        request = ProcessEmailRequest(
            # Earlier replies quoted here were typed by the owner, so a name in them is hidden too.
            thread_context=await names.hide(thread_context(message, thread, details)),
            email_body=details.renumber(str(message.id), message.body_masked or ""),
            rag_context=format_rag_context(chunks),
            tone=TONE_PROMPTS[tone],
            sign_off=details.owner or "",
            provider=provider,
            **await _style_fields(message),
        )
        try:
            generated = await _call_agent("/process-email", request, ProcessEmailResponse)
        except httpx.HTTPStatusError as exc:
            refused = agent_client.refusal_egress(exc.response)
            if exc.response.status_code == 403:
                logger.error("agent authentication failed: AGENT_TOKEN is missing or mismatched (HTTP 403)")
                raise
            if not agent_client.is_content_refusal(exc.response):
                raise
            generated = _not_drafted(_agent_error_code(exc.response))
        refused = generated.pop("egress", refused)
        return names.restore_answer(generated) | {"rag_sources": _source_records(chunks)}
    except (httpx.HTTPError, EmbeddingError, ValueError, DocumentMaskingError) as exc:
        logger.warning("draft generation failed for message %s: %s", message.id, exc)
        return {}
    finally:
        # Whatever already went to a model is recorded, a failed run included.
        await save_egress([*searched, *refused], user_id=message.user_id, message_id=message.id)


def _generation_fields(generated: dict) -> dict:
    # NULL, not 0.0: an NA message was never scored, and coercing that to zero made "not
    # evaluated" indistinguishable from "the critic rejected this" in every stored statistic.
    return {
        "ai_summary": generated.get("summary") or "",
        "draft_reply": generated.get("draft") or "",
        "action_items": generated.get("action_items") or [],
        "rag_sources": generated.get("rag_sources") or [],
        **_review_fields(generated),
        "generated_at": datetime.now(timezone.utc),
    }


async def _generate_and_store(
    message: Message,
    thread: list[Message] | None = None,
    tone: Tone = Tone.PROFESSIONAL,
    details: ThreadMap | None = None,
) -> GenerationOutcome:
    """Generate the Lane C draft and store it.

    An "NA" result (no reply needed) is stored too, so the poller stops retrying it. A failure
    counts an attempt and leaves the message for a later try. Nothing is written to a sent message.
    """
    if refusal_for(message, Action.DRAFT):
        return GenerationOutcome.SKIPPED  # covers drafting on open and the poller alike
    details = details or await _details_for(message, thread or [])
    generated = await _generate(message, tone, thread or [], details)
    if generated.get(NOT_DRAFTED) and message.draft_reply:
        return GenerationOutcome.KEPT  # a regenerate failed for content keeps the reviewed draft
    is_usable = bool(generated) and (bool(generated.get("draft")) or generated.get("category") == "NA")
    # Counted in SQL: two failures at once both count, where a value read before the call would lose one.
    fields = ({**_generation_fields(generated), "draft_tone": tone} if is_usable
              else {"generation_attempts": Message.generation_attempts + 1})
    if not await _update_unsent(message.id, fields):
        return GenerationOutcome.SKIPPED
    if not is_usable:
        message.generation_attempts = (message.generation_attempts or 0) + 1
        return GenerationOutcome.FAILED
    for column, value in fields.items():
        setattr(message, column, value)
    await audit(AuditAction.GENERATE_DRAFT, user_id=message.user_id, message=message.id, tone=tone,
                confidence=message.critic_confidence, review=message.needs_human_review)
    return GenerationOutcome.STORED if fields.get("draft_reply") else GenerationOutcome.NO_REPLY


async def _mark_read(pk: UUID) -> None:
    """Set once, so the first-open time is kept rather than bumped on every revisit."""
    async with get_sessionmaker()() as session:
        await session.execute(
            update(Message).where(Message.id == pk, Message.read_at.is_(None))
            .values(read_at=func.now())
        )
        await session.commit()


async def read_email(message_id: str, *, scope: Scope, viewer_id: UUID | None = None) -> DashboardEmail | None:
    """The email as the reader opens it: opening the detail view is the moment a person reads it."""
    email = await email_detail(message_id, scope=scope, viewer_id=viewer_id)
    if email is None:
        return None
    await _mark_read(UUID(email.id))
    return email.model_copy(update={"isRead": True})


async def mark_unread(message_id: str, *, scope: Scope) -> bool:
    """Back to unread, to come back to later. False when it is not the caller's."""
    try:
        pk = UUID(message_id)
    except ValueError:
        return False
    async with get_sessionmaker()() as session, session.begin():
        changed = await session.scalar(update(Message).where(Message.id == pk, scope.where(Message.user_id))
                                       .values(read_at=None).returning(Message.id))
    return changed is not None


async def email_detail(message_id: str, *, scope: Scope, viewer_id: UUID | None = None) -> DashboardEmail | None:
    """The email with its draft and thread, read-only: it does not change whether it was read."""
    try:
        pk = UUID(message_id)
    except ValueError:
        return None
    loaded = await _load_with_thread(pk, scope)
    if loaded is None:
        return None
    message, thread = loaded
    # Never drafted here: the request returns at once and the worker drafts it within seconds.
    if is_drafting(message):
        await request_draft(pk)
    # One session for the reads: one pooled connection per open, not one per read.
    async with get_sessionmaker()() as session:
        details = await _details_for(message, thread, session)
        email = _to_email(message, await _policy_for(message, session), thread=thread, details=details,
                          egress=await egress_for(message.id, session),
                          schedule=(await states_for([pk], session)).get(pk), sent=await _gmail_replies(message, session),
                          has_unread_attachment=await has_unread_attachment(message, session))
        # Templates are the viewer's; a script, which has no viewer, gets the owner's.
        email.suggestedTemplateId = await suggested_template_id(
            viewer_id or message.user_id, f"{message.subject or ''}\n{message.body_masked or ''}", session)
    return email


async def email_for_thread(
    thread_id: str, *, scope: Scope, viewer_id: UUID | None = None
) -> DashboardEmail | None:
    """The newest of the caller's messages in a Gmail thread, as the detail view returns it.

    The Chrome extension knows only the thread Gmail has open, not AIMail's message id.
    """
    stmt = (select(Message.id)
            .where(Message.thread_id == thread_id, scope.where(Message.user_id))
            .order_by(Message.received_at.desc().nulls_last(), Message.created_at.desc())
            .limit(1))
    async with get_sessionmaker()() as session:
        pk = await session.scalar(stmt)
    if pk is None:
        return None
    return await read_email(str(pk), scope=scope, viewer_id=viewer_id)


async def confirm_sender(message_id: str, *, scope: Scope) -> DashboardEmail | None:
    """The owner checked a flagged sender and says they are real; drafting resumes on the next open.

    Only spoof_detected moves, so a passing email is never relabelled and a repeat is harmless.
    """
    try:
        pk = UUID(message_id)
    except ValueError:
        return None
    loaded = await _load_with_thread(pk, scope)
    if loaded is None:
        return None
    message, thread = loaded
    if message.is_spoofed:
        async with get_sessionmaker()() as session, session.begin():
            await session.execute(update(Message).where(
                Message.id == pk, Message.auth_status == AuthStatus.SPOOF_DETECTED,
            ).values(auth_status=AuthStatus.SENDER_CONFIRMED, generation_attempts=0))
            record(session, AuditAction.CONFIRM_SENDER, user_id=message.user_id, message=message_id)
        message.auth_status = AuthStatus.SENDER_CONFIRMED
    return _to_email(message, await _policy_for(message), thread=thread, details=await _details_for(message, thread),
                     sent=await _gmail_replies(message))


async def regenerate_email(
    message_id: str, *, scope: Scope, tone: Tone = Tone.PROFESSIONAL
) -> DashboardEmail | None:
    """A fresh draft in the given tone (Regenerate / tone change).

    The old draft stays if it fails, and the failure is raised as DraftNotUpdatedError so the
    reader is told rather than shown the old draft as if it were new.
    """
    try:
        pk = UUID(message_id)
    except ValueError:
        return None
    loaded = await _load_with_thread(pk, scope)
    if loaded is None:
        return None
    message, thread = loaded
    _require(message, Action.REDRAFT)
    details = await _details_for(message, thread)
    outcome = await _generate_and_store(message, thread, tone, details)
    _raise_unless_updated(message, outcome)
    return _to_email(message, await _policy_for(message), thread=thread, details=details,
                     sent=await _gmail_replies(message))


def _raise_unless_updated(message: Message, outcome: GenerationOutcome) -> None:
    if outcome in (GenerationOutcome.STORED, GenerationOutcome.NO_REPLY):
        return
    if outcome is GenerationOutcome.KEPT:
        raise DraftNotUpdatedError(ErrorCode.DRAFT_REFUSED)
    if outcome is GenerationOutcome.FAILED:
        raise DraftNotUpdatedError(ErrorCode.AGENT_UNAVAILABLE)
    _require(message, Action.REDRAFT)
    raise AlreadySentError(str(message.id))  # SKIPPED with nothing refused: it was sent while generating


# Longer than a Gmail send can take (its timeout is 30 s): a claim this new with no Gmail id is still going.
SEND_IN_FLIGHT = timedelta(minutes=2)


def _is_mid_send(message: Message) -> bool:
    """Claimed by another request that has not heard back from Gmail yet; "sent" could be untrue."""
    is_recent_claim = message.sent_at is not None and message.sent_at > datetime.now(timezone.utc) - SEND_IN_FLIGHT
    return is_recent_claim and message.sent_message_id is None


async def _claim_send(pk: UUID) -> bool:
    """Mark the message sent before sending, atomically. False if another request already has.

    Claim-then-act: two clicks or two tabs cannot both pass a read-then-check, and a send that
    Gmail accepted can never be retried because something failed after it.
    """
    async with get_sessionmaker()() as session:
        claimed = await session.scalar(
            update(Message)
            .where(Message.id == pk, Message.sent_at.is_(None))
            .values(sent_at=func.now(), send_outcome_unknown_at=func.now())
            .returning(Message.id)
        )
        await session.commit()
    return claimed is not None


async def _release_send_claim(pk: UUID) -> None:
    """Undo a claim whose send failed, so the reply can be approved again."""
    async with get_sessionmaker()() as session:
        await session.execute(update(Message).where(Message.id == pk).values(sent_at=None, send_outcome_unknown_at=None))
        await session.commit()


async def _get(session: AsyncSession, pk: UUID, scope: Scope) -> Message | None:
    """A message by id, only if it is in the caller's scope: anyone else's reads as missing."""
    return await session.scalar(select(Message).where(Message.id == pk, scope.where(Message.user_id)))


async def _load(pk: UUID, scope: Scope) -> Message | None:
    async with get_sessionmaker()() as session:
        return await _get(session, pk, scope)


async def approve_and_send(
    message_id: str, draft: str, *, scope: Scope, remind: bool | None = None
) -> DashboardEmail | None:
    """Send the approved (possibly edited) draft as a reply, then record what was sent.

    A message already sent is returned unchanged; one another request is sending right now is refused with
    SEND_IN_PROGRESS. No database connection is held while Gmail is called. Raises SendError if the send fails.
    """
    try:
        pk = UUID(message_id)
    except ValueError:
        return None
    message = await _load(pk, scope)
    if message is None:
        return None
    _require(message, Action.SEND)
    thread = await _thread_for(message)
    details = await _details_for(message, thread)
    reply = _outgoing(draft, details)
    if message.user_id is not None and not await connections.can_send(message.user_id):
        raise SendRejectedError(ErrorCode.SEND_NOT_GRANTED)
    if _is_mid_send(message):
        raise DomainError(ErrorCode.SEND_IN_PROGRESS, f"message {message_id} is being sent by another request")
    if message.sent_at is not None:
        # Sent before this request: answering is idempotent.
        return _to_email(message, await _policy_for(message), thread=thread, details=details,
                     sent=await _gmail_replies(message))
    if not await _claim_send(pk):
        # Another request claimed it a moment ago and may still fail; showing "sent" now could be untrue.
        raise DomainError(ErrorCode.SEND_IN_PROGRESS, f"message {message_id} is being sent by another request")
    try:
        sent = await send_reply(
            message.gmail_message_id, message.from_addr or "", message.subject or "", reply.sent,
            owner_id=message.user_id,
        )
    except SendOutcomeUnknownError:
        # The claim stays: Gmail may have sent, and releasing it would invite a second copy. The mark
        # is what lets the reconciler settle it later (app/send_reconciler.py).
        await mark_outcome_unknown(Message, pk)
        await audit(AuditAction.SEND_OUTCOME_UNKNOWN, user_id=message.user_id, success=False,
                    message=message_id)
        raise
    except SendError:
        await _release_send_claim(pk)
        # The failed attempt is the row an auditor most wants; log before unwinding.
        await audit(AuditAction.APPROVE_AND_SEND, user_id=message.user_id, success=False,
                    message=message_id)
        raise
    try:
        stored, is_learning_style = await _record_send(pk, message, reply, sent, remind)
    except SQLAlchemyError:
        return await _sent_but_not_recorded(message, reply, sent)
    if is_learning_style:
        await _relearn_after_send(stored.user_id)
        await remember_reply(stored.user_id, pk, message.body_masked or "", reply.stored)
    # Sent now, by hand: a reply held for later must not go out as a second copy.
    if await cancel_pending(pk, CancelReason.SENT_MANUALLY):
        await audit(AuditAction.SCHEDULED_SEND_CANCELLED, user_id=message.user_id, message=message_id,
                    reason=CancelReason.SENT_MANUALLY)
    return _to_email(stored, await _policy_for(stored), thread=thread, details=details,
                     sent=await _gmail_replies(stored))


async def _record_send(pk: UUID, message: Message, reply: OutgoingReply, sent: SentReply,
                       remind: bool | None = None) -> tuple[Message, bool]:
    """What was sent, with its audit row in the same transaction; and whether style learning is on."""
    async with get_sessionmaker()() as session:
        stored = await session.get(Message, pk)
        is_learning_style = await is_learning(session, stored.user_id)
        if is_learning_style:
            # Both sides in placeholder form, so the learner never sees a real detail.
            stored.draft_shown = stored.draft_reply or ""
            stored.edit_ratio = edit_ratio(stored.draft_shown, reply.stored)
        # The record keeps placeholders, so no detail sits readable outside its vault.
        stored.draft_reply = reply.stored
        stored.sent_message_id = sent.message_id
        stored.send_outcome_unknown_at = None
        # Rows ingested before migration 0009 learn their thread from the send.
        stored.thread_id = stored.thread_id or sent.thread_id
        # In the same transaction: the trail records this send exactly when the record of it commits.
        record(session, AuditAction.APPROVE_AND_SEND, user_id=message.user_id, message=str(pk),
               restored=reply.restored)
        # For the to-do's waiting list; the listener's Sent watch sees the same send and is ignored.
        # If the listener stored it first, the user's Remind me and the link to the email still land.
        await session.execute(insert(SentMessage).values(
            user_id=stored.user_id, gmail_id=sent.gmail_id, message_id=pk, thread_id=stored.thread_id,
            sent_at=func.now(), subject=stored.subject or "", body_masked=reply.stored, remind=remind,
        ).on_conflict_do_update(index_elements=["gmail_id"], set_={
            # The listener's copy was masked apart, with other placeholder numbers: ours shares the vault.
            "remind": remind, "message_id": pk, "body_masked": reply.stored, "subject": stored.subject or ""}))
        await session.commit()
        return stored, is_learning_style


async def _sent_but_not_recorded(message: Message, reply: OutgoingReply, sent: SentReply) -> DashboardEmail:
    """Gmail sent it but saving the record failed. The reader is told the truth, that it was sent, rather than
    shown an error they would answer by sending again; the claim already stored blocks a second copy. Not
    handed to the reconciler, which releases a claim it cannot match in Gmail."""
    logger.exception("reply %s was sent (Gmail id %s) but its record was not saved", message.id, sent.message_id)
    await audit(AuditAction.APPROVE_AND_SEND, user_id=message.user_id, message=message.id,
                gmail_message=sent.message_id, recorded=False)
    message.draft_reply = reply.stored
    message.sent_message_id = sent.message_id
    message.sent_at = message.sent_at or datetime.now(timezone.utc)
    # The policy read would hit the database that just failed; the list shows the owner's priority again.
    return _to_email(message)


async def _relearn_after_send(user_id: UUID) -> None:
    """The reply is already sent, so a learning failure is logged and never reported as a send error."""
    try:
        async with get_sessionmaker()() as session, session.begin():
            await relearn(session, user_id)
    except SQLAlchemyError:
        logger.exception("writing style: relearning failed for user %s", user_id)


async def _style_fields(message: Message) -> dict:
    """The user's writing style for a reply to this email, in its language; masked when stored."""
    if message.user_id is None:
        return {"style_hint": "", "style_examples": []}  # unowned rows have no style to look up
    async with get_sessionmaker()() as session:
        style = await style_for(session, message.user_id, detect_language(message.body_masked or ""))
    return {"style_hint": style.hint, "style_examples": style.examples}


def _stored_rag_context(message: Message) -> str:
    """The policy passages the draft was grounded on, rebuilt from what generation stored."""
    return rag_context_of(message.rag_sources)


async def _refine(
    message: Message, thread: list[Message], draft: str, instruction: str, details: ThreadMap, tone: Tone
) -> dict:
    """Lane C's revision plus its review. Raises DraftNotUpdatedError when nothing usable came back.

    The user typed the draft and the instruction, so their details and any new name are hidden
    before they leave, and the names go back into the revision (specs/features/privacy-gaps.md).
    """
    names = TypedNames()
    request = AgentRefineRequest(
        email_body=details.renumber(str(message.id), message.body_masked or ""),
        draft=await names.hide(details.for_model(draft)),
        instruction=await names.hide(details.for_model(instruction)),
        tone=TONE_PROMPTS[tone],
        thread_context=await names.hide(thread_context(message, thread, details)),
        rag_context=_stored_rag_context(message),
        # Stored with any typed name put back, so hidden again before it leaves.
        action_items=[await names.hide(item) for item in message.action_items or []],
        sign_off=details.owner or "",
        provider=await model_for(message.user_id),
        **await _style_fields(message),
    )
    try:
        refined = await _call_agent("/refine", request, RefineResponse)
    except httpx.HTTPStatusError as exc:
        logger.warning("refine failed for message %s: %s", message.id, exc)
        await save_egress(agent_client.refusal_egress(exc.response), user_id=message.user_id, message_id=message.id)
        if exc.response.status_code == 403:
            logger.error("agent authentication failed: AGENT_TOKEN is missing or mismatched (HTTP 403)")
            raise DomainError(ErrorCode.FORBIDDEN, "agent authentication failed") from exc
        if agent_client.is_content_refusal(exc.response):
            raise DraftNotUpdatedError(ErrorCode.DRAFT_REFUSED) from exc
        raise DraftNotUpdatedError(ErrorCode.AGENT_UNAVAILABLE) from exc
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("refine failed for message %s: %s", message.id, exc)
        raise DraftNotUpdatedError(ErrorCode.AGENT_UNAVAILABLE) from exc
    await save_egress(refined.pop("egress", []), user_id=message.user_id, message_id=message.id)
    if not refined.get("draft"):
        raise DraftNotUpdatedError(ErrorCode.AGENT_UNAVAILABLE)
    return names.restore_answer(refined)




AGENT_ERROR = "agent_error"


def _agent_error_code(response: httpx.Response) -> str:
    """A code only, never the agent's detail text: a validation error echoes the request body."""
    try:
        detail = response.json().get("detail")
    except ValueError:
        return AGENT_ERROR
    if isinstance(detail, dict):
        return str(detail.get("code", AGENT_ERROR))
    return detail if isinstance(detail, str) and detail.startswith("gemini_") else AGENT_ERROR


def _translation_refusal(response: httpx.Response) -> ErrorCode:
    """The agent's own codes are internal; the reader is told unfaithful, or try again later."""
    is_unfaithful = _agent_error_code(response) == ErrorCode.TRANSLATION_UNFAITHFUL
    return ErrorCode.TRANSLATION_UNFAITHFUL if is_unfaithful else ErrorCode.AGENT_UNAVAILABLE


class TranslationError(DomainError):
    """Translation was refused (unfaithful) or the agent could not produce one."""


# Which error a refused action raises, so each route answers with the type its callers expect.
_REFUSAL_ERROR: dict[Action, type[DomainError]] = {
    Action.REDRAFT: DraftNotUpdatedError, Action.REFINE: DraftNotUpdatedError,
    Action.SEND: SendRejectedError, Action.TRANSLATE: TranslationError, Action.FOLLOW_UP: SendRejectedError,
}


async def translate_email(message_id: str, language: str, *, scope: Scope) -> dict | None:
    """The masked body in another language. Not stored: it is a reading aid, regenerated on ask.

    Only masked text is sent, so this reaches the model with nothing drafting did not already send.
    """
    try:
        pk = UUID(message_id)
    except ValueError:
        return None
    message = await _load(pk, scope)
    if message is None:
        return None
    _require(message, Action.TRANSLATE)
    details = await _details_for(message, await _thread_for(message))
    text = details.renumber(str(message.id), plain_text(message.body_masked or ""))
    if len(text) > MAX_TRANSLATE_CHARS:
        raise TranslationError(ErrorCode.TOO_LARGE, "email too long to translate")
    try:
        translated = await _call_agent("/translate", TranslateRequest(
            text=text, language=language, provider=await model_for(message.user_id)), TranslateResponse)
    except httpx.HTTPStatusError as exc:
        await save_egress(agent_client.refusal_egress(exc.response), user_id=message.user_id, message_id=message.id)
        await audit(AuditAction.TRANSLATE_EMAIL, user_id=message.user_id, success=False,
                    message=message_id, language=language)
        raise TranslationError(_translation_refusal(exc.response)) from exc
    except httpx.HTTPError as exc:
        raise TranslationError(ErrorCode.AGENT_UNAVAILABLE, "agent unreachable") from exc
    await audit(AuditAction.TRANSLATE_EMAIL, user_id=message.user_id, message=message_id,
                language=language)
    await save_egress(translated.pop("egress", []), user_id=message.user_id, message_id=message.id)
    return translated


async def refine_email(
    message_id: str, instruction: str, draft: str, *, scope: Scope, tone: Tone = Tone.PROFESSIONAL
) -> DashboardEmail | None:
    """Revise the draft per a user instruction and store it (dashboard's Refine box)."""
    try:
        pk = UUID(message_id)
    except ValueError:
        return None
    loaded = await _load_with_thread(pk, scope)
    if loaded is None:
        return None
    message, thread = loaded
    _require(message, Action.REFINE)
    details = await _details_for(message, thread)
    try:
        refined = await _refine(message, thread, draft, instruction, details, tone)
    except DraftNotUpdatedError:
        await audit(AuditAction.REFINE_DRAFT, user_id=message.user_id, success=False,
                    message=message_id)
        raise
    # The old verdict described the old draft; the refined one carries its own.
    fields = {"draft_reply": refined["draft"], "draft_tone": tone, **_review_fields(refined)}
    if not await _update_unsent(pk, fields):
        raise AlreadySentError(message_id)
    for column, value in fields.items():
        setattr(message, column, value)
    await audit(AuditAction.REFINE_DRAFT, user_id=message.user_id, message=message_id,
                review=message.needs_human_review)
    return _to_email(message, await _policy_for(message), thread=thread, details=details,
                     sent=await _gmail_replies(message))


ADAPT_INSTRUCTION = (
    "Rewrite this saved template as the reply to this email. Keep the user's wording and structure. "
    "Where the template has a {{variable}}, fill it only with what the email itself states; leave any "
    "other {{variable}} exactly as written, braces included."
)


def filled_template(template: ReplyTemplate, details: ThreadMap) -> str:
    """The template with the variables AIMail can fill: names as placeholders, and today's date."""
    today = format_day(datetime.now(ZoneInfo(TEMPLATE_TIMEZONE)).date(), Language(template.language))
    return fill_variables(template.body, sender=details.sender, owner=details.owner, today=today)


async def fill_template(message_id: str, template: ReplyTemplate, *, scope: Scope) -> str | None:
    """The template filled for this email, for the editor; nothing is stored or sent to a model."""
    try:
        pk = UUID(message_id)
    except ValueError:
        return None
    loaded = await _load_with_thread(pk, scope)
    if loaded is None:
        return None
    message, thread = loaded
    _require(message, Action.REFINE)
    return filled_template(template, await _details_for(message, thread))


async def adapt_template(
    message_id: str, template: ReplyTemplate, *, scope: Scope, tone: Tone = Tone.PROFESSIONAL
) -> DashboardEmail | None:
    """The agent rewrites the filled template for this email; reviewed and stored like a refine."""
    filled = await fill_template(message_id, template, scope=scope)
    if filled is None:
        return None
    return await refine_email(message_id, ADAPT_INSTRUCTION, filled, scope=scope, tone=tone)


async def translate_template(template: ReplyTemplate, language: Language) -> str:
    """The template in another language, every {{variable}} kept, for the user to check and save.

    Only masked typed text leaves, as in a refine: a phone number in the template comes back as a
    marker the user retypes, and a name goes back in after translation.
    """
    names = TypedNames()
    # Variables first, so a name check can never touch the inside of a {{variable}}.
    protected, variables = protect_variables(mask_typed_text(template.body))
    protected = await names.hide(protected)
    if len(protected) > MAX_TRANSLATE_CHARS:
        raise TranslationError(ErrorCode.TOO_LARGE, "template too long to translate")
    try:
        translated = await _call_agent("/translate", TranslateRequest(
            text=protected, language=language, provider=await model_for(template.user_id)), TranslateResponse)
    except httpx.HTTPStatusError as exc:
        await save_egress(agent_client.refusal_egress(exc.response), user_id=template.user_id, message_id=None)
        raise TranslationError(_translation_refusal(exc.response)) from exc
    except httpx.HTTPError as exc:
        raise TranslationError(ErrorCode.AGENT_UNAVAILABLE, "agent unreachable") from exc
    await save_egress(translated.pop("egress", []), user_id=template.user_id, message_id=None)
    restored = restore_variables(translated["text"], variables)
    if restored is None:
        raise TranslationError(ErrorCode.TRANSLATION_UNFAITHFUL, "a template variable was lost")
    return names.restore(restored)


async def translate_draft(message_id: str, text: str, *, scope: Scope) -> dict | None:
    """A reply the reader wrote in their own language, in the email's language, for them to check and send
    (specs/features/write-in-my-language.md). Nothing is stored; the send path checks it as any draft.

    Only masked text leaves, as in a refine: known details become their placeholders, new fixed formats
    are masked, and typed names are hidden and put back after. Returned in placeholder form.
    """
    try:
        pk = UUID(message_id)
    except ValueError:
        return None
    loaded = await _load_with_thread(pk, scope)
    if loaded is None:
        return None
    message, thread = loaded
    _require(message, Action.REFINE)
    details = await _details_for(message, thread)
    language = detect_language(plain_text(message.body_masked or ""))
    names = TypedNames()
    masked = await names.hide(details.for_model(text))
    if len(masked) > MAX_TRANSLATE_CHARS:
        raise TranslationError(ErrorCode.TOO_LARGE, "reply too long to translate")
    try:
        translated = await _call_agent("/translate", TranslateRequest(
            text=masked, language=language, provider=await model_for(message.user_id)), TranslateResponse)
    except httpx.HTTPStatusError as exc:
        await save_egress(agent_client.refusal_egress(exc.response), user_id=message.user_id, message_id=message.id)
        await audit(AuditAction.TRANSLATE_EMAIL, user_id=message.user_id, success=False, message=message_id,
                    language=language, draft=True)
        raise TranslationError(_translation_refusal(exc.response)) from exc
    except httpx.HTTPError as exc:
        raise TranslationError(ErrorCode.AGENT_UNAVAILABLE, "agent unreachable") from exc
    await save_egress(translated.pop("egress", []), user_id=message.user_id, message_id=message.id)
    await audit(AuditAction.TRANSLATE_EMAIL, user_id=message.user_id, message=message_id, language=language,
                draft=True)
    return {"language": language, "text": names.restore(translated["text"])}


def _check_ahead(when: datetime) -> datetime:
    """A send or snooze time in the future and within MAX_SCHEDULE_AHEAD_DAYS, as an aware UTC time."""
    if when.tzinfo is None:
        raise DomainError(ErrorCode.TIME_OUT_OF_RANGE, "the time needs a timezone")
    now = datetime.now(timezone.utc)
    if not now < when <= now + timedelta(days=MAX_SCHEDULE_AHEAD_DAYS):
        raise DomainError(ErrorCode.TIME_OUT_OF_RANGE, "the time must be ahead, and not too far")
    return when.astimezone(timezone.utc)


async def _with_schedule(message: Message) -> DashboardEmail:
    # The whole email, as opening it gives: the view replaces its copy, and a bare one lost Show details.
    thread = await _thread_for(message)
    return _to_email(message, await _policy_for(message), thread=thread, details=await _details_for(message, thread),
                     schedule=(await states_for([message.id])).get(message.id), sent=await _gmail_replies(message))


async def schedule_email(message_id: str, draft: str, send_at: datetime, *, scope: Scope) -> DashboardEmail | None:
    """Hold the approved draft until send_at. Checked now as a send would be, and again when due."""
    try:
        pk = UUID(message_id)
    except ValueError:
        return None
    message = await _load(pk, scope)
    if message is None:
        return None
    _require(message, Action.SEND)
    if message.sent_at is not None:
        # Send refuses nothing for a sent email (a repeat is answered as sent); a schedule would say
        # "Scheduled" for something that will never go.
        raise AlreadySentError(message_id)
    when = _check_ahead(send_at)
    # The real details behind the draft's placeholders are deleted then; it could not be sent.
    vault_days = get_settings().vault_retention_days
    if vault_days != KEEP_FOREVER and when > message.created_at + timedelta(days=vault_days):
        raise DomainError(ErrorCode.TIME_OUT_OF_RANGE, "after this email's details are deleted")
    reply = _outgoing(draft, await _details_for(message, await _thread_for(message)))
    await hold(pk, message.user_id, reply.stored, when)
    await audit(AuditAction.SEND_SCHEDULED, user_id=message.user_id, message=message_id)
    return await _with_schedule(message)


async def cancel_schedule(message_id: str, *, scope: Scope) -> DashboardEmail | None:
    try:
        pk = UUID(message_id)
    except ValueError:
        return None
    message = await _load(pk, scope)
    if message is None:
        return None
    if await cancel_pending(pk, CancelReason.CANCELLED):
        await audit(AuditAction.SCHEDULED_SEND_CANCELLED, user_id=message.user_id, message=message_id,
                    reason=CancelReason.CANCELLED)
    return await _with_schedule(message)


async def snooze_email(message_id: str, until: datetime | None, *, scope: Scope) -> DashboardEmail | None:
    """Out of the inbox until then, and unread when it comes back; None brings it back now."""
    try:
        pk = UUID(message_id)
    except ValueError:
        return None
    message = await _load(pk, scope)
    if message is None:
        return None
    fields = {"snoozed_until": _check_ahead(until), "read_at": None} if until else {"snoozed_until": None}
    async with get_sessionmaker()() as session, session.begin():
        await session.execute(update(Message).where(Message.id == pk).values(**fields))
    for column, value in fields.items():
        setattr(message, column, value)
    await audit(AuditAction.EMAIL_SNOOZED, user_id=message.user_id, message=message_id, snoozed=until is not None)
    return await _with_schedule(message)


FOLLOW_UP_INSTRUCTION = (
    "They have not answered this reply. Rewrite it as a short, polite follow-up: say you are following "
    "up, remind them in one line of what you asked, and ask again. Two or three sentences, in the same "
    "language as the reply, keeping its greeting and sign-off."
)


async def _follow_up_target(sent_id: str, scope: Scope) -> tuple[SentMessage, Message, list[Message]] | None:
    """A sent reply of this user's and the email it answered, with that email's thread.

    Only replies sent through AIMail: their placeholders share the email's vault, so names restore
    correctly. A reply sent from Gmail was masked apart, with nothing to restore it from.
    """
    try:
        pk = UUID(sent_id)
    except ValueError:
        return None
    async with get_sessionmaker()() as session:
        sent = await session.scalar(select(SentMessage).where(SentMessage.id == pk, scope.where(SentMessage.user_id)))
        answered = await _get(session, sent.message_id, scope) if sent and sent.message_id else None
        is_stale = sent is not None and await _is_no_longer_waiting(session, sent)
    if sent is None:
        return None
    if sent.followed_up_at is not None:
        raise SendRejectedError(ErrorCode.ALREADY_SENT)  # its follow-up went out, or is going now
    if answered is None:
        raise SendRejectedError(ErrorCode.FOLLOW_UP_UNAVAILABLE)
    if is_stale:
        raise SendRejectedError(ErrorCode.FOLLOW_UP_STALE)
    _require(answered, Action.FOLLOW_UP)
    return sent, answered, await _thread_for(answered)


async def _is_no_longer_waiting(session: AsyncSession, sent: SentMessage) -> bool:
    """Checked again at send time, as the To-do list checked it: a page left open goes stale."""
    if sent.dismissed_at is not None:
        return True
    in_thread = (Message.thread_id == sent.thread_id, Message.user_id.is_not_distinct_from(sent.user_id))
    newer_send = select(SentMessage.id).where(
        SentMessage.thread_id == sent.thread_id, SentMessage.user_id.is_not_distinct_from(sent.user_id),
        SentMessage.sent_at > sent.sent_at)
    answered_since = select(Message.id).where(*in_thread, Message.created_at > sent.sent_at)
    return bool(await session.scalar(select(newer_send.exists() | answered_since.exists())))


async def draft_follow_up(sent_id: str, *, scope: Scope) -> tuple[str, list[Detail]] | None:
    """A follow-up to an unanswered reply, written by the agent from that reply. Not stored.

    Returned with the details of the thread it is numbered in, so the page fills in the same names
    the send will.
    """
    target = await _follow_up_target(sent_id, scope)
    if target is None:
        return None
    sent, answered, thread = target
    details = await _details_for(answered, thread)
    refined = await _refine(answered, thread, sent.body_masked, FOLLOW_UP_INSTRUCTION, details, Tone.PROFESSIONAL)
    return refined["draft"], [Detail(**detail) for detail in details.details()]


async def _claim_follow_up(sent_id: UUID) -> bool:
    """Claim-then-send, as for a reply: a second click finds the claim and sends nothing."""
    async with get_sessionmaker()() as session, session.begin():
        claimed = await session.scalar(
            update(SentMessage).where(SentMessage.id == sent_id, SentMessage.followed_up_at.is_(None))
            .values(followed_up_at=func.now()).returning(SentMessage.id))
    return claimed is not None


async def _release_follow_up(sent_id: UUID) -> None:
    async with get_sessionmaker()() as session, session.begin():
        await session.execute(update(SentMessage).where(SentMessage.id == sent_id).values(followed_up_at=None))


async def send_follow_up(sent_id: str, draft: str, *, scope: Scope) -> bool:
    """Send the approved follow-up in the email's thread, through the same checks as a reply.

    False when the reply is not the user's. Raises SendRejectedError, SendError or
    SendOutcomeUnknownError as approve_and_send does.
    """
    target = await _follow_up_target(sent_id, scope)
    if target is None:
        return False
    sent, answered, thread = target
    reply = _outgoing(draft, await _details_for(answered, thread))
    if answered.user_id is not None and not await connections.can_send(answered.user_id):
        raise SendRejectedError(ErrorCode.SEND_NOT_GRANTED)
    if not await _claim_follow_up(sent.id):
        raise DomainError(ErrorCode.SEND_IN_PROGRESS, f"a follow-up to {sent_id} is already being sent")
    try:
        gmail = await send_reply(answered.gmail_message_id, answered.from_addr or "", answered.subject or "",
                                 reply.sent, owner_id=answered.user_id)
    except SendOutcomeUnknownError:
        # The claim stays: Gmail may have sent it. The reconciler asks Gmail later and releases it if not.
        await mark_follow_up_unknown(sent.id)
        await audit(AuditAction.SEND_OUTCOME_UNKNOWN, user_id=answered.user_id, success=False, sent=sent_id)
        raise
    except SendError:
        await _release_follow_up(sent.id)
        await audit(AuditAction.FOLLOW_UP_SENT, user_id=answered.user_id, success=False, sent=sent_id)
        raise
    try:
        await _record_follow_up(sent, answered, reply, gmail)
    except SQLAlchemyError:
        # Sent, so the reader is told so; the claim blocks a second copy, and the Sent watch records it.
        logger.exception("follow-up to %s was sent (Gmail id %s) but its record was not saved", sent_id, gmail.message_id)
        await audit(AuditAction.FOLLOW_UP_SENT, user_id=answered.user_id, sent=sent_id, recorded=False)
    return True


async def _record_follow_up(sent: SentMessage, answered: Message, reply: OutgoingReply, gmail: SentReply) -> None:
    """The follow-up becomes the thread's latest send, so the waiting clock restarts from it.

    The link to the answered email moves to it too, so it can be followed up in turn.
    """
    async with get_sessionmaker()() as session, session.begin():
        await session.execute(update(SentMessage).where(SentMessage.id == sent.id).values(message_id=None))
        await session.execute(insert(SentMessage).values(
            user_id=sent.user_id, gmail_id=gmail.gmail_id, message_id=answered.id,
            thread_id=answered.thread_id or sent.thread_id, sent_at=func.now(), subject=sent.subject,
            body_masked=reply.stored, remind=True,
        ).on_conflict_do_update(index_elements=["gmail_id"], set_={
            "message_id": answered.id, "remind": True, "body_masked": reply.stored, "subject": sent.subject}))
        record(session, AuditAction.FOLLOW_UP_SENT, user_id=answered.user_id, message=str(answered.id),
               restored=reply.restored)
