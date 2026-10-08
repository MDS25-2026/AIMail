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
from enum import Enum
from uuid import UUID

import httpx
from pydantic import BaseModel
from sqlalchemy import func, select, tuple_, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app import agent_client, connections
from app.agent_contract import (
    MAX_TRANSLATE_CHARS,
    TONE_PROMPTS,
    ProcessEmailRequest,
    ProcessEmailResponse,
    RefineResponse,
    Tone,
    TranslateRequest,
    TranslateResponse,
)
from app.agent_contract import RefineRequest as AgentRefineRequest
from app.audit import AuditAction, audit, record
from app.contracts import (
    ContextChunk,
    DashboardEmail,
    Detail,
    EgressRecord,
    EmailPage,
    MeasureView,
    QuantityView,
    Source,
    ThreadMessage,
)
from app.core.cursor import Cursor
from app.core.errors import DomainError, ErrorCode
from app.core.language import detect_language
from app.core.ownership import EVERYTHING, Scope
from app.core.redaction import PLACEHOLDER, has_redaction_marker
from app.core.vault import ThreadMap, build_thread_map
from app.db.models import AuthStatus, MaskingStatus, Message, ModelEgress, UserProfile
from app.db.session import get_sessionmaker
from app.egress_log import egress_for, save_egress
from app.email_policy import Action, refusal_for
from app.gmail_send import SendError, SendOutcomeUnknownError, send_reply
from app.jobs import (
    claim_for_drafting,
    claim_requested,
    release_drafting,
    request_draft,
)
from app.ml.category import predict_category
from app.normalise.quantities import quantities_in
from app.past_replies import remember_reply
from app.personalisation import DEFAULT_POLICY, Policy, apply_policy, load_policy
from app.plain_text import plain_text
from app.private_mode import provider_for
from app.rag.errors import EmbeddingError
from app.rag.retrieve import retrieve
from app.rag.utils import format_rag_context
from app.send_reconciler import mark_outcome_unknown
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


def is_drafting(message: Message) -> bool:
    """A first draft is on its way: none yet, not sent, allowed, and not already tried and failed."""
    return (message.generated_at is None and message.sent_at is None and not refusal_for(message, Action.DRAFT)
            and not message.generation_attempts)


def _to_email(
    message: Message,
    policy: Policy = DEFAULT_POLICY,
    thread: list[Message] | None = None,
    details: ThreadMap | None = None,
    egress: list[ModelEgress] | None = None,
) -> DashboardEmail:
    details = details or ThreadMap()
    key = str(message.id)
    category_val = message.category
    category_conf = message.category_confidence
    if category_val is None:
        cat_enum, conf = predict_category(message.body_masked or message.snippet_masked or "")
        category_val = cat_enum.value
        category_conf = conf

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
        category=category_val,
        categoryConfidence=category_conf,
        threadContext=_thread_view(thread or [], details),
        aiSummary=message.ai_summary or "",
        actionItems=message.action_items or [],
        draftReply=message.draft_reply or "",
        tone=Tone(message.draft_tone or Tone.PROFESSIONAL),
        isDrafting=is_drafting(message),
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
        egress=[_egress_view(row) for row in egress or []],
    )


def _egress_view(row: ModelEgress) -> EgressRecord:
    return EgressRecord(purpose=row.purpose, provider=row.provider, chars=row.chars, hidden=row.hidden or {},
                        caught=row.caught, at=row.created_at.isoformat() if row.created_at else "")


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


async def list_dashboard_emails(scope: Scope, policy_email: str, limit: int, after: Cursor | None) -> EmailPage:
    """Newest first, one page; id breaks ties, so two emails stored in the same instant both appear."""
    statement = select(Message).where(scope.where(Message.user_id))
    if after:
        statement = statement.where(tuple_(Message.created_at, Message.id) < (after.created_at, after.row_id))
    # One extra row says whether another page exists without a count query.
    statement = statement.order_by(Message.created_at.desc(), Message.id.desc()).limit(limit + 1)
    async with get_sessionmaker()() as session:
        rows = (await session.scalars(statement)).all()
        policy = await load_policy(session, policy_email)
    page = rows[:limit]
    is_more = len(rows) > limit
    return EmailPage(emails=[_to_email(message, policy, details=_own_details(message)) for message in page],
                     nextCursor=Cursor(page[-1].created_at, page[-1].id).encode() if is_more else None)


def _own_details(message: Message) -> ThreadMap:
    """One email's details in its own numbering, for its inbox row (subject and preview)."""
    text = f"{message.subject or ''}\n{message.snippet_masked or ''}"
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
            "needs_human_review": True, "review_reasons": [f"no draft: {code}"], NOT_DRAFTED: True}


def _source_records(chunks: list[ContextChunk]) -> list[dict]:
    return [
        {"label": chunk["source_title"] or "Policy", "chunkId": str(chunk["chunk_id"]),
         "excerpt": chunk["content"], "score": round(chunk["similarity_score"], 3)}
        for chunk in chunks
    ]


async def _generate(message: Message, tone: Tone, thread: list[Message], details: ThreadMap) -> dict:
    """Retrieve policy context (Lane B) and call Lane C's /process-email. Returns {} on any failure.

    The chunks ride along under "rag_sources" so the caller stores what the draft was grounded on.
    """
    try:
        provider = await provider_for(message.user_id)
        with track_egress() as searched:
            chunks = await retrieve(message.body_masked or "", k=5, scope=Scope(owner_id=message.user_id),
                                    provider=provider)
        request = ProcessEmailRequest(
            thread_context=thread_context(message, thread, details),
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
            if exc.response.status_code != AGENT_CONTENT_FAILURE:
                raise
            generated = _not_drafted(_agent_error_code(exc.response))
        await save_egress([*searched, *generated.pop("egress", [])], user_id=message.user_id, message_id=message.id)
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
            "prompt_version": reviewed.get("prompt_version") or "",
        },
        "needs_human_review": bool(reviewed.get("needs_human_review")),
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
    # Never drafted here: the request returns at once and the worker drafts it within seconds.
    if is_drafting(message):
        await request_draft(pk)
    # Opening the detail view is the moment a person actually reads it.
    await _mark_read(pk)
    message.read_at = message.read_at or datetime.now(timezone.utc)
    return _to_email(message, thread=thread, details=details, egress=await egress_for(message.id))


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
    return _to_email(message, thread=thread, details=await _details_for(message, thread))


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
    return _to_email(message, thread=thread, details=details)


def _raise_unless_updated(message: Message, outcome: GenerationOutcome) -> None:
    if outcome in (GenerationOutcome.STORED, GenerationOutcome.NO_REPLY):
        return
    if outcome is GenerationOutcome.KEPT:
        raise DraftNotUpdatedError(ErrorCode.DRAFT_REFUSED)
    if outcome is GenerationOutcome.FAILED:
        raise DraftNotUpdatedError(ErrorCode.AGENT_UNAVAILABLE)
    _require(message, Action.REDRAFT)
    raise AlreadySentError(str(message.id))  # SKIPPED with nothing refused: it was sent while generating


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
    _require(message, Action.SEND)
    reply = _outgoing(draft, await _details_for(message, await _thread_for(message)))
    if message.user_id is not None and not await connections.can_send(message.user_id):
        raise SendRejectedError(ErrorCode.SEND_NOT_GRANTED)
    if message.sent_at is not None or not await _claim_send(pk):
        return _to_email(await _load(pk, scope) or message)
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
        # In the same transaction: the trail records this send exactly when the record of it commits.
        record(session, AuditAction.APPROVE_AND_SEND, user_id=message.user_id, message=message_id,
               restored=reply.restored)
        await session.commit()
        email = _to_email(stored)
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


async def _style_fields(message: Message) -> dict:
    """The user's writing style for a reply to this email, in its language; masked when stored."""
    if message.user_id is None:
        return {"style_hint": "", "style_examples": []}  # unowned rows have no style to look up
    async with get_sessionmaker()() as session:
        style = await style_for(session, message.user_id, detect_language(message.body_masked or ""))
    return {"style_hint": style.hint, "style_examples": style.examples}


def _stored_rag_context(message: Message) -> str:
    """The policy passages the draft was grounded on, rebuilt from what generation stored."""
    return "\n\n".join(f"[{source.get('label', 'Policy')}] {source.get('excerpt', '')}"
                       for source in message.rag_sources or [])


async def _refine(
    message: Message, thread: list[Message], draft: str, instruction: str, details: ThreadMap, tone: Tone
) -> dict:
    """Lane C's revision plus its review. Raises DraftNotUpdatedError when nothing usable came back.

    The user typed the draft and the instruction, so fixed-format details are masked before they
    leave; names stay, since they were typed on purpose.
    """
    request = AgentRefineRequest(
        email_body=details.renumber(str(message.id), message.body_masked or ""),
        draft=details.for_model(draft),
        instruction=details.for_model(instruction),
        tone=TONE_PROMPTS[tone],
        thread_context=thread_context(message, thread, details),
        rag_context=_stored_rag_context(message),
        action_items=message.action_items or [],
        sign_off=details.owner or "",
        provider=await provider_for(message.user_id),
        **await _style_fields(message),
    )
    try:
        refined = await _call_agent("/refine", request, RefineResponse)
    except httpx.HTTPStatusError as exc:
        logger.warning("refine failed for message %s: %s", message.id, exc)
        if exc.response.status_code == AGENT_CONTENT_FAILURE:
            raise DraftNotUpdatedError(ErrorCode.DRAFT_REFUSED) from exc
        raise DraftNotUpdatedError(ErrorCode.AGENT_UNAVAILABLE) from exc
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("refine failed for message %s: %s", message.id, exc)
        raise DraftNotUpdatedError(ErrorCode.AGENT_UNAVAILABLE) from exc
    await save_egress(refined.pop("egress", []), user_id=message.user_id, message_id=message.id)
    if not refined.get("draft"):
        raise DraftNotUpdatedError(ErrorCode.AGENT_UNAVAILABLE)
    return refined




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
    Action.SEND: SendRejectedError, Action.TRANSLATE: TranslationError,
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
            text=text, language=language, provider=await provider_for(message.user_id)), TranslateResponse)
    except httpx.HTTPStatusError as exc:
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
    return _to_email(message, thread=thread, details=details)
