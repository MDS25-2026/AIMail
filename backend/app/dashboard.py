"""Assembly of the dashboard email view (Lane D shape) from the `messages` table.

`list_dashboard_emails` is the fast list (Lane A fields + Lane B priority, no generation).
`email_detail` returns a single email with the Lane C generation. It generates once (retrieve
policy context via Lane B, call Lane C's /process-email) and caches the result on the row, so
reopening serves stored text instead of regenerating. Generation is best-effort: if Lane C is
unreachable the email still returns with its Lane A/B fields and stays uncached for a later retry.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum, StrEnum
from uuid import UUID

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app import connections
from app.audit import audit
from app.contracts import (
    ContextChunk,
    DashboardEmail,
    Detail,
    MeasureView,
    QuantityView,
    Source,
    ThreadMessage,
)
from app.core.config import get_settings
from app.core.logging_setup import request_id
from app.core.middleware import REQUEST_ID_HEADER
from app.core.ownership import EVERYTHING, Scope
from app.core.redaction import PLACEHOLDER, has_redaction_marker
from app.core.vault import ThreadMap, build_thread_map
from app.db.models import MaskingStatus, Message, UserProfile
from app.db.session import get_sessionmaker
from app.gmail_send import SendError, SendOutcomeUnknownError, send_reply
from app.normalise.quantities import quantities_in
from app.past_replies import remember_reply
from app.personalisation import DEFAULT_POLICY, Policy, apply_policy, load_policy
from app.plain_text import plain_text
from app.private_mode import provider_for
from app.rag.embed import EmbeddingError
from app.rag.retrieve import retrieve
from app.rag.utils import format_rag_context
from app.writing_style import edit_ratio, is_learning, relearn, style_for

logger = logging.getLogger(__name__)

AGENT_TIMEOUT_SECONDS = 120


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


def _thread_view(thread: list[Message], details: ThreadMap) -> list[ThreadMessage]:
    """Each message in the thread, with the owner's reply right under the one it answered."""
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
    return view


def _to_email(
    message: Message,
    policy: Policy = DEFAULT_POLICY,
    thread: list[Message] | None = None,
    details: ThreadMap | None = None,
) -> DashboardEmail:
    details = details or ThreadMap()
    key = str(message.id)
    return DashboardEmail(
        id=key,
        sender=message.from_addr or "",
        subject=details.renumber(key, message.subject or ""),
        preview=details.renumber(key, message.snippet_masked or ""),
        body=details.renumber(key, message.body_masked or ""),
        timestamp=(message.received_at or message.created_at).isoformat(),
        authStatus=message.auth_status or "pass",
        # The classifier's prediction, then the user's policy on top of it.
        priority=apply_policy(message, policy),
        threadContext=_thread_view(thread or [], details),
        aiSummary=message.ai_summary or "",
        actionItems=message.action_items or [],
        draftReply=message.draft_reply or "",
        tone="professional",
        sources=[Source(**source) for source in message.rag_sources or []],
        piiMasked=bool((message.emails_masked or 0) + (message.phones_masked or 0)),
        criticConfidence=message.critic_confidence or 0.0,
        sentAt=message.sent_at.isoformat() if message.sent_at else None,
        isRead=message.read_at is not None,
        quantities=_quantity_views(message.body_masked or ""),
        masking=message.masking_status or MaskingStatus.COMPLETE,
        replyTo=message.reply_to or None,
        threadId=message.thread_id,
        details=[Detail(**detail) for detail in details.details()],
    )


async def _owner_name(owner_id: UUID | None) -> str:
    if owner_id is None:
        return ""
    async with get_sessionmaker()() as session:
        return await session.scalar(select(UserProfile.display_name).where(UserProfile.id == owner_id)) or ""


async def _details_for(message: Message, thread: list[Message]) -> ThreadMap:
    """The conversation's placeholders and their values, oldest message first, plus the owner's
    name as the sign-off placeholder. Opened per request and never stored or logged."""
    ordered = sorted([*thread, message], key=lambda m: m.received_at or m.created_at or datetime.min.replace(tzinfo=timezone.utc))
    return build_thread_map(
        [(str(m.id), m.pii_vault, m.user_id, m.gmail_message_id or "",
          f"{m.subject or ''}\n{m.snippet_masked or ''}\n{m.body_masked or ''}") for m in ordered],
        await _owner_name(message.user_id),
    )


async def _thread_for(message: Message) -> list[Message]:
    if not message.thread_id:
        return []
    async with get_sessionmaker()() as session:
        return await _thread_of(session, message)


async def list_dashboard_emails(scope: Scope, policy_email: str, limit: int = 50) -> list[DashboardEmail]:
    stmt = (select(Message).where(scope.where(Message.user_id))
            .order_by(Message.created_at.desc()).limit(limit))
    async with get_sessionmaker()() as session:
        rows = (await session.scalars(stmt)).all()
        policy = await load_policy(session, policy_email)
    return [_to_email(message, policy, details=_own_details(message)) for message in rows]


def _own_details(message: Message) -> ThreadMap:
    """One email's details in its own numbering, for its inbox row (subject and preview)."""
    text = f"{message.subject or ''}\n{message.snippet_masked or ''}"
    return build_thread_map(
        [(str(message.id), message.pii_vault, message.user_id, message.gmail_message_id or "", text)], ""
    )


# A message whose drafting fails this many times is left for a human instead of being retried
# every poll cycle, which would spend quota and hold back the messages behind it.
MAX_GENERATION_ATTEMPTS = 5


class AlreadySentError(RuntimeError):
    """The draft of a sent message is the record of what went out; it is never replaced."""


class DraftErrorCode(StrEnum):
    AGENT_UNAVAILABLE = "agent_unavailable"  # the agent or retrieval failed; try again later
    DRAFT_REFUSED = "draft_refused"  # the model failed on this content; the old draft stays
    MASKING_PENDING = "masking_pending"  # quarantined: there is nothing masked to draft from


class DraftNotUpdatedError(RuntimeError):
    """A regenerate or refine that changed nothing. Answering 200 with the old draft hid it."""

    def __init__(self, code: DraftErrorCode, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


class SendErrorCode(StrEnum):
    REDACTION_MARKERS = "redaction_markers"  # "[Redacted]" would reach the recipient as written
    MASKING_PENDING = "masking_pending"  # quarantined: there is nothing safe to reply to yet
    SEND_NOT_GRANTED = "send_not_granted"  # the owner allowed AIMail to read their Gmail, not send
    # A placeholder with no known value: invented by the model, or its vault expired or will not open.
    UNRESOLVED_PLACEHOLDERS = "unresolved_placeholders"


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
        raise SendRejectedError(SendErrorCode.UNRESOLVED_PLACEHOLDERS, 422)
    if has_redaction_marker(sent):
        raise SendRejectedError(SendErrorCode.REDACTION_MARKERS, 422)
    return OutgoingReply(stored=stored, sent=sent, restored=len(PLACEHOLDER.findall(stored)))


class SendRejectedError(RuntimeError):
    """A draft refused before anything is claimed or sent; the dashboard's own check can be bypassed."""

    def __init__(self, code: SendErrorCode, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


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
    stmt = (
        select(Message.id)
        .where(
            Message.generated_at.is_(None),
            Message.masking_status == MaskingStatus.COMPLETE,
            Message.auth_status != "spoof_detected",
            Message.generation_attempts < MAX_GENERATION_ATTEMPTS,
        )
        .order_by(Message.generation_attempts, Message.created_at.desc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    async with get_sessionmaker()() as session:
        pending = (await session.scalars(stmt)).all()
    generated = 0
    for pk in pending:
        loaded = await _load_with_thread(pk, EVERYTHING)
        if loaded and await _generate_and_store(*loaded) is GenerationOutcome.STORED:
            generated += 1
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


_TONE_PROMPTS = {
    "professional": "professional, concise, and collaborative",
    "casual": "casual, warm, and friendly",
}


async def _call_agent(path: str, payload: dict) -> dict:
    """POST to Lane C, carrying this request's id so both services' logs line up."""
    url = get_settings().email_agent_url.rstrip("/") + path
    # Lane C runs a multi-step pipeline under its own 100 s deadline; this sits just above it.
    async with httpx.AsyncClient(timeout=AGENT_TIMEOUT_SECONDS) as client:
        response = await client.post(
            url, json=payload, headers={REQUEST_ID_HEADER: request_id.get()}
        )
        response.raise_for_status()
        return response.json()


# The agent's "this will fail the same way every time" status (cut off, blocked, rejected input).
AGENT_CONTENT_FAILURE = 422


NOT_DRAFTED = "not_drafted"


def _not_drafted(code: str) -> dict:
    """Stored like an NA route: a human handles it, and the poller stops retrying a failure that
    repeats at temperature 0 and would otherwise spend quota every cycle."""
    return {"category": "NA", "draft": None, "summary": "", "action_items": [],
            "needs_human_review": True, "review_reasons": [f"no draft: {code}"], NOT_DRAFTED: True}


def _source_records(chunks: list[ContextChunk]) -> list[dict]:
    return [
        {"label": chunk["source_title"] or "Policy", "chunkId": str(chunk["chunk_id"]),
         "excerpt": chunk["content"], "score": round(chunk["similarity_score"], 3)}
        for chunk in chunks
    ]


async def _generate(message: Message, tone: str, thread: list[Message], details: ThreadMap) -> dict:
    """Retrieve policy context (Lane B) and call Lane C's /process-email. Returns {} on any failure.

    The chunks ride along under "rag_sources" so the caller stores what the draft was grounded on.
    """
    try:
        provider = await provider_for(message.user_id)
        chunks = await retrieve(message.body_masked or "", k=5, scope=Scope(owner_id=message.user_id),
                                provider=provider)
        payload = {
            "thread_context": thread_context(message, thread, details),
            "email_body": details.renumber(str(message.id), message.body_masked or ""),
            "rag_context": format_rag_context(chunks),
            "tone": _TONE_PROMPTS.get(tone, _TONE_PROMPTS["professional"]),
            "sign_off": details.owner or "",
            "provider": provider,
            **await _style_fields(message.user_id),
        }
        try:
            generated = await _call_agent("/process-email", payload)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != AGENT_CONTENT_FAILURE:
                raise
            generated = _not_drafted(_agent_error_code(exc.response))
        return generated | {"rag_sources": _source_records(chunks)}
    except (httpx.HTTPError, EmbeddingError, ValueError) as exc:
        logger.warning("draft generation failed for message %s: %s", message.id, exc)
        return {}


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


def _review_fields(reviewed: dict) -> dict:
    """The critic's verdict on a draft, stored the same way for a generated and a refined one."""
    confidence = reviewed.get("confidence")
    return {
        "critic_confidence": None if confidence is None else float(confidence),
        # Stored so a rescued draft is distinguishable from a first-pass success.
        "critic_attempts": int(reviewed.get("attempts") or 0),
        "critic_checks": {
            "grounding_ok": reviewed.get("grounding_ok"),
            "pii_clean": reviewed.get("pii_clean"),
            "tone_match": reviewed.get("tone_match"),
            "completeness": reviewed.get("completeness"),
            "pii_findings": reviewed.get("pii_findings") or [],
            "review_reasons": reviewed.get("review_reasons") or [],
            # Which models answered and how many retries it took; outcomes and ms, no content.
            "model_calls": reviewed.get("model_calls") or [],
        },
        "needs_human_review": bool(reviewed.get("needs_human_review")),
    }


async def _generate_and_store(
    message: Message,
    thread: list[Message] | None = None,
    tone: str = "professional",
    details: ThreadMap | None = None,
) -> GenerationOutcome:
    """Generate the Lane C draft and store it.

    An "NA" result (no reply needed) is stored too, so the poller stops retrying it. A failure
    counts an attempt and leaves the message for a later try. Nothing is written to a sent message.
    """
    if not message.is_masked:
        return GenerationOutcome.SKIPPED  # quarantined (#109): no masked content to draft from yet
    details = details or await _details_for(message, thread or [])
    generated = await _generate(message, tone, thread or [], details)
    if generated.get(NOT_DRAFTED) and message.draft_reply:
        return GenerationOutcome.KEPT  # a regenerate failed for content keeps the reviewed draft
    is_usable = bool(generated) and (bool(generated.get("draft")) or generated.get("category") == "NA")
    fields = (_generation_fields(generated) if is_usable
              else {"generation_attempts": (message.generation_attempts or 0) + 1})
    if not await _update_unsent(message.id, fields):
        return GenerationOutcome.SKIPPED
    for column, value in fields.items():
        setattr(message, column, value)
    if not is_usable:
        return GenerationOutcome.FAILED
    await audit("generate_draft", f"message={message.id} tone={tone} "
                f"confidence={message.critic_confidence} review={message.needs_human_review}")
    return GenerationOutcome.STORED if fields.get("draft_reply") else GenerationOutcome.NO_REPLY


async def _mark_read(pk: UUID) -> None:
    """Set once, so the first-open time is kept rather than bumped on every revisit."""
    async with get_sessionmaker()() as session:
        await session.execute(
            update(Message).where(Message.id == pk, Message.read_at.is_(None))
            .values(read_at=func.now())
        )
        await session.commit()


async def email_detail(message_id: str, *, scope: Scope) -> DashboardEmail | None:
    try:
        pk = UUID(message_id)
    except ValueError:
        return None
    loaded = await _load_with_thread(pk, scope)
    if loaded is None:
        return None
    message, thread = loaded
    details = await _details_for(message, thread)
    if message.generated_at is None and message.sent_at is None:
        await _generate_and_store(message, thread, details=details)
    # Opening the detail view is the moment a person actually reads it.
    await _mark_read(pk)
    message.read_at = message.read_at or datetime.now(timezone.utc)
    return _to_email(message, thread=thread, details=details)


async def email_for_thread(thread_id: str, *, scope: Scope) -> DashboardEmail | None:
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
    return await email_detail(str(pk), scope=scope)


async def regenerate_email(
    message_id: str, *, scope: Scope, tone: str = "professional"
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
    if message.sent_at is not None:
        raise AlreadySentError(message_id)
    details = await _details_for(message, thread)
    outcome = await _generate_and_store(message, thread, tone, details)
    _raise_unless_updated(message, outcome)
    return _to_email(message, thread=thread, details=details)


def _raise_unless_updated(message: Message, outcome: GenerationOutcome) -> None:
    if outcome in (GenerationOutcome.STORED, GenerationOutcome.NO_REPLY):
        return
    if outcome is GenerationOutcome.KEPT:
        raise DraftNotUpdatedError(DraftErrorCode.DRAFT_REFUSED, 422)
    if outcome is GenerationOutcome.FAILED:
        raise DraftNotUpdatedError(DraftErrorCode.AGENT_UNAVAILABLE, 502)
    if not message.is_masked:
        raise DraftNotUpdatedError(DraftErrorCode.MASKING_PENDING, 409)
    raise AlreadySentError(str(message.id))  # SKIPPED on a masked row: sent while generating


async def _claim_send(pk: UUID) -> bool:
    """Mark the message sent before sending, atomically. False if another request already has.

    Claim-then-act: two clicks or two tabs cannot both pass a read-then-check, and a send that
    Gmail accepted can never be retried because something failed after it.
    """
    async with get_sessionmaker()() as session:
        claimed = await session.scalar(
            update(Message)
            .where(Message.id == pk, Message.sent_at.is_(None))
            .values(sent_at=func.now())
            .returning(Message.id)
        )
        await session.commit()
    return claimed is not None


async def _release_send_claim(pk: UUID) -> None:
    """Undo a claim whose send failed, so the reply can be approved again."""
    async with get_sessionmaker()() as session:
        await session.execute(update(Message).where(Message.id == pk).values(sent_at=None))
        await session.commit()


async def _get(session: AsyncSession, pk: UUID, scope: Scope) -> Message | None:
    """A message by id, only if it is in the caller's scope: anyone else's reads as missing."""
    return await session.scalar(select(Message).where(Message.id == pk, scope.where(Message.user_id)))


async def _load(pk: UUID, scope: Scope) -> Message | None:
    async with get_sessionmaker()() as session:
        return await _get(session, pk, scope)


async def approve_and_send(message_id: str, draft: str, *, scope: Scope) -> DashboardEmail | None:
    """Send the approved (possibly edited) draft as a reply, then record what was sent.

    Idempotent: a message already sent (or being sent by another request) is returned unchanged.
    No database connection is held while Gmail is called. Raises SendError if the send fails.
    """
    try:
        pk = UUID(message_id)
    except ValueError:
        return None
    message = await _load(pk, scope)
    if message is None:
        return None
    if not message.is_masked:
        raise SendRejectedError(SendErrorCode.MASKING_PENDING, 409)
    reply = _outgoing(draft, await _details_for(message, await _thread_for(message)))
    if message.user_id is not None and not await connections.can_send(message.user_id):
        raise SendRejectedError(SendErrorCode.SEND_NOT_GRANTED, 403)
    if message.sent_at is not None or not await _claim_send(pk):
        return _to_email(await _load(pk, scope) or message)
    try:
        sent = await send_reply(
            message.gmail_message_id, message.from_addr or "", message.subject or "", reply.sent,
            owner_id=message.user_id,
        )
    except SendOutcomeUnknownError:
        # The claim stays: Gmail may have sent, and releasing it would invite a second copy.
        await audit("send_outcome_unknown", f"message={message_id}", success=False)
        raise
    except SendError:
        await _release_send_claim(pk)
        # The failed attempt is the row an auditor most wants; log before unwinding.
        await audit("approve_and_send", f"message={message_id}", success=False)
        raise
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
        # Rows ingested before migration 0009 learn their thread from the send.
        stored.thread_id = stored.thread_id or sent.thread_id
        await session.commit()
        email = _to_email(stored)
    await audit("approve_and_send", f"message={message_id} restored={reply.restored}")
    if is_learning_style:
        await _relearn_after_send(stored.user_id)
        await remember_reply(stored.user_id, pk, message.body_masked or "", reply.stored)
    return email


async def _relearn_after_send(user_id: UUID) -> None:
    """The reply is already sent, so a learning failure is logged and never reported as a send error."""
    try:
        async with get_sessionmaker()() as session, session.begin():
            await relearn(session, user_id)
    except SQLAlchemyError:
        logger.exception("writing style: relearning failed for user %s", user_id)


async def _style_fields(user_id: UUID | None) -> dict:
    """The user's writing style for a draft request; masked when stored, so it can go as is."""
    async with get_sessionmaker()() as session:
        style = await style_for(session, user_id)
    return {"style_hint": style.hint, "style_examples": style.examples}


def _stored_rag_context(message: Message) -> str:
    """The policy passages the draft was grounded on, rebuilt from what generation stored."""
    return "\n\n".join(f"[{source.get('label', 'Policy')}] {source.get('excerpt', '')}"
                       for source in message.rag_sources or [])


async def _refine(
    message: Message, thread: list[Message], draft: str, instruction: str, details: ThreadMap
) -> dict:
    """Lane C's revision plus its review. Raises DraftNotUpdatedError when nothing usable came back.

    The user typed the draft and the instruction, so fixed-format details are masked before they
    leave; names stay, since they were typed on purpose.
    """
    payload = {
        "email_body": details.renumber(str(message.id), message.body_masked or ""),
        "draft": details.for_model(draft),
        "instruction": details.for_model(instruction),
        "thread_context": thread_context(message, thread, details),
        "rag_context": _stored_rag_context(message),
        "action_items": message.action_items or [],
        "sign_off": details.owner or "",
        "provider": await provider_for(message.user_id),
        **await _style_fields(message.user_id),
    }
    try:
        refined = await _call_agent("/refine", payload)
    except httpx.HTTPStatusError as exc:
        logger.warning("refine failed for message %s: %s", message.id, exc)
        if exc.response.status_code == AGENT_CONTENT_FAILURE:
            raise DraftNotUpdatedError(DraftErrorCode.DRAFT_REFUSED, 422) from exc
        raise DraftNotUpdatedError(DraftErrorCode.AGENT_UNAVAILABLE, 502) from exc
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("refine failed for message %s: %s", message.id, exc)
        raise DraftNotUpdatedError(DraftErrorCode.AGENT_UNAVAILABLE, 502) from exc
    if not refined.get("draft"):
        raise DraftNotUpdatedError(DraftErrorCode.AGENT_UNAVAILABLE, 502)
    return refined


# Mirrors the agent's own bound (email_agent.MAX_TRANSLATE_CHARS), checked here first so an
# over-long body gets a clear answer instead of a validation error that echoes the body back.
MAX_TRANSLATE_CHARS = 12_000
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


class TranslationError(RuntimeError):
    """Translation was refused (unfaithful) or the agent could not produce one."""

    def __init__(self, code: str, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


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
    if not message.is_masked:
        raise TranslationError("masking_pending", 409)
    details = await _details_for(message, await _thread_for(message))
    text = details.renumber(str(message.id), plain_text(message.body_masked or ""))
    if len(text) > MAX_TRANSLATE_CHARS:
        raise TranslationError("email_too_long_to_translate", 413)
    try:
        translated = await _call_agent("/translate", {"text": text, "language": language,
                                                      "provider": await provider_for(message.user_id)})
    except httpx.HTTPStatusError as exc:
        await audit("translate_email", f"message={message_id} language={language}", success=False)
        raise TranslationError(_agent_error_code(exc.response), exc.response.status_code) from exc
    except httpx.HTTPError as exc:
        raise TranslationError("agent_unreachable", 502) from exc
    await audit("translate_email", f"message={message_id} language={language}")
    return translated


async def refine_email(
    message_id: str, instruction: str, draft: str, *, scope: Scope
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
    if message.sent_at is not None:
        raise AlreadySentError(message_id)
    if not message.is_masked:
        raise DraftNotUpdatedError(DraftErrorCode.MASKING_PENDING, 409)
    details = await _details_for(message, thread)
    try:
        refined = await _refine(message, thread, draft, instruction, details)
    except DraftNotUpdatedError:
        await audit("refine_draft", f"message={message_id}", success=False)
        raise
    # The old verdict described the old draft; the refined one carries its own.
    fields = {"draft_reply": refined["draft"], **_review_fields(refined)}
    if not await _update_unsent(pk, fields):
        raise AlreadySentError(message_id)
    for column, value in fields.items():
        setattr(message, column, value)
    await audit("refine_draft", f"message={message_id} review={message.needs_human_review}")
    return _to_email(message, thread=thread, details=details)
