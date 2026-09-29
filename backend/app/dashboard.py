"""Assembly of the dashboard email view (Lane D shape) from the `messages` table.

`list_dashboard_emails` is the fast list (Lane A fields + Lane B priority, no generation).
`email_detail` returns a single email with the Lane C generation. It generates once (retrieve
policy context via Lane B, call Lane C's /process-email) and caches the result on the row, so
reopening serves stored text instead of regenerating. Generation is best-effort: if Lane C is
unreachable the email still returns with its Lane A/B fields and stays uncached for a later retry.
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import audit
from app.contracts import (
    ContextChunk,
    DashboardEmail,
    MeasureView,
    QuantityView,
    Source,
    ThreadMessage,
)
from app.core.config import get_settings
from app.core.logging_setup import request_id
from app.core.middleware import REQUEST_ID_HEADER
from app.db.models import MaskingStatus, Message
from app.db.session import get_sessionmaker
from app.gmail_send import SendError, send_reply
from app.normalise.quantities import quantities_in
from app.personalisation import DEFAULT_POLICY, Policy, apply_policy, load_policy
from app.plain_text import plain_text
from app.rag.embed import EmbeddingError
from app.rag.retrieve import retrieve
from app.rag.utils import format_rag_context

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
            Message.id != message.id,
            Message.masking_status == MaskingStatus.COMPLETE,
        )
        .order_by(Message.received_at)
    )
    return list((await session.scalars(stmt)).all())


def thread_context(message: Message, thread: list[Message]) -> str:
    """Earlier messages for the model, labelled by position. Never by sender: from_addr is stored
    unmasked and is documented as never entering a model payload."""
    before = [m for m in thread if m.received_at and message.received_at
              and m.received_at < message.received_at][-THREAD_CONTEXT_MESSAGES:]
    return "\n\n".join(
        f"Earlier message {index}:\n{(m.body_masked or '')[:THREAD_CONTEXT_CHARS_EACH]}"
        for index, m in enumerate(before, 1)
    )


def _thread_view(thread: list[Message]) -> list[ThreadMessage]:
    return [ThreadMessage(sender=m.from_addr or "", snippet=m.snippet_masked or "") for m in thread]


def _to_email(
    message: Message, policy: Policy = DEFAULT_POLICY, thread: list[Message] | None = None
) -> DashboardEmail:
    return DashboardEmail(
        id=str(message.id),
        sender=message.from_addr or "",
        subject=message.subject or "",
        preview=message.snippet_masked or "",
        body=message.body_masked or "",
        timestamp=(message.received_at or message.created_at).isoformat(),
        # The classifier's prediction, then the user's policy on top of it.
        priority=apply_policy(message, policy),
        threadContext=_thread_view(thread or []),
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
    )


async def list_dashboard_emails(limit: int = 50) -> list[DashboardEmail]:
    stmt = select(Message).order_by(Message.created_at.desc()).limit(limit)
    async with get_sessionmaker()() as session:
        rows = (await session.scalars(stmt)).all()
        policy = await load_policy(session, get_settings().mailbox_owner_email)
    return [_to_email(message, policy) for message in rows]


async def generate_pending(limit: int | None = None) -> int:
    """Generate + cache drafts for messages without one; return how many were generated.

    Shared by the `make generate` script (no limit) and the background poller (small batch, to stay
    under Gemini's free-tier rate limit). Commits per message to keep progress on a mid-run failure.
    """
    generated = 0
    async with get_sessionmaker()() as session:
        stmt = select(Message).where(
            Message.generated_at.is_(None), Message.masking_status == MaskingStatus.COMPLETE
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        pending = (await session.scalars(stmt)).all()
        for message in pending:
            if await _generate_and_store(message, thread=await _thread_of(session, message)):
                generated += 1
            await session.commit()
    return generated


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


def _source_records(chunks: list[ContextChunk]) -> list[dict]:
    return [
        {"label": chunk["source_title"] or "Policy", "chunkId": str(chunk["chunk_id"]),
         "excerpt": chunk["content"], "score": round(chunk["similarity_score"], 3)}
        for chunk in chunks
    ]


async def _generate(message: Message, tone: str, thread: list[Message]) -> dict:
    """Retrieve policy context (Lane B) and call Lane C's /process-email. Returns {} on any failure.

    The chunks ride along under "rag_sources" so the caller stores what the draft was grounded on.
    """
    try:
        chunks = await retrieve(message.body_masked or "", k=5)
        payload = {
            "thread_context": thread_context(message, thread),
            "email_body": message.body_masked or "",
            "rag_context": format_rag_context(chunks),
            "tone": _TONE_PROMPTS.get(tone, _TONE_PROMPTS["professional"]),
        }
        return await _call_agent("/process-email", payload) | {"rag_sources": _source_records(chunks)}
    except (httpx.HTTPError, EmbeddingError, ValueError) as exc:
        logger.warning("draft generation failed for message %s: %s", message.id, exc)
        return {}


async def _generate_and_store(
    message: Message, tone: str = "professional", thread: list[Message] | None = None
) -> bool:
    """Generate the Lane C draft and cache it on the message; return True if a draft was stored.

    Caches a real draft, and also an "NA" result (the agent decided no reply is needed, e.g. a
    notification) so the poller stops retrying it. A non-NA empty draft is a transient failure and
    left uncached to retry. The caller owns committing the session.
    """
    if not message.is_masked:
        return False  # quarantined (#109): there is no masked content to draft from yet
    generated = await _generate(message, tone, thread or [])
    if not generated:  # {} means the call failed (rate limit / error) — leave uncached to retry
        return False
    draft = generated.get("draft") or ""
    if not draft and generated.get("category") != "NA":
        return False
    message.ai_summary = generated.get("summary") or ""
    message.draft_reply = draft
    message.action_items = generated.get("action_items") or []
    message.rag_sources = generated.get("rag_sources") or []
    # NULL, not 0.0: an NA message was never scored, and coercing that to zero made "not
    # evaluated" indistinguishable from "the critic rejected this" in every stored statistic.
    confidence = generated.get("confidence")
    message.critic_confidence = None if confidence is None else float(confidence)
    # The agent already reports this; storing it is what makes a rescued draft
    # distinguishable from a first-pass success.
    message.critic_attempts = int(generated.get("attempts") or 0)
    message.critic_checks = {
        "grounding_ok": generated.get("grounding_ok"),
        "pii_clean": generated.get("pii_clean"),
        "tone_match": generated.get("tone_match"),
        "completeness": generated.get("completeness"),
        "pii_findings": generated.get("pii_findings") or [],
        "review_reasons": generated.get("review_reasons") or [],
        # Which models answered and how many retries it took; no content, only outcomes and ms.
        "model_calls": generated.get("model_calls") or [],
    }
    message.needs_human_review = bool(generated.get("needs_human_review"))
    message.generated_at = datetime.now(timezone.utc)
    await audit(
        "generate_draft",
        f"message={message.id} tone={tone} confidence={message.critic_confidence} "
        f"review={message.needs_human_review}",
    )
    return bool(draft)


async def email_detail(message_id: str) -> DashboardEmail | None:
    try:
        pk = UUID(message_id)
    except ValueError:
        return None
    async with get_sessionmaker()() as session:
        message = await session.get(Message, pk)
        if message is None:
            return None
        thread = await _thread_of(session, message)
        if message.generated_at is None:
            await _generate_and_store(message, thread=thread)
        # Opening the detail view is the moment a person actually reads it. Set once so the
        # first-open time is preserved rather than being bumped on every revisit.
        if message.read_at is None:
            message.read_at = datetime.now(timezone.utc)
        email = _to_email(message, thread=thread)
        await session.commit()
        return email


async def regenerate_email(message_id: str, tone: str = "professional") -> DashboardEmail | None:
    """Force a fresh draft in the given tone, replacing any cached one (Regenerate / tone change)."""
    try:
        pk = UUID(message_id)
    except ValueError:
        return None
    async with get_sessionmaker()() as session:
        message = await session.get(Message, pk)
        if message is None:
            return None
        message.generated_at = None
        thread = await _thread_of(session, message)
        await _generate_and_store(message, tone, thread)
        email = _to_email(message, thread=thread)
        await session.commit()
        return email


async def approve_and_send(message_id: str, draft: str) -> DashboardEmail | None:
    """Send the approved (possibly edited) draft as a reply, then mark the message sent.

    Idempotent: a message already sent is returned unchanged. Raises SendError if Gmail send fails.
    """
    try:
        pk = UUID(message_id)
    except ValueError:
        return None
    async with get_sessionmaker()() as session:
        message = await session.get(Message, pk)
        if message is None:
            return None
        if message.sent_at is None:
            try:
                sent = await send_reply(
                    message.gmail_message_id, message.from_addr or "", message.subject or "", draft
                )
            except SendError:
                # The failed attempt is the row an auditor most wants; log before unwinding.
                await audit("approve_and_send", f"message={message_id}", success=False)
                raise
            message.draft_reply = draft
            message.sent_at = datetime.now(timezone.utc)
            message.sent_message_id = sent.message_id
            # Rows ingested before migration 0009 learn their thread from the send.
            message.thread_id = message.thread_id or sent.thread_id
            await audit("approve_and_send", f"message={message_id}")
        email = _to_email(message)
        await session.commit()
        return email


async def _refine(message: Message, draft: str, instruction: str) -> str | None:
    """Call Lane C's /refine to revise a draft per a user instruction. None on failure."""
    try:
        payload = {"email_body": message.body_masked or "", "draft": draft, "instruction": instruction}
        return (await _call_agent("/refine", payload)).get("draft")
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("refine failed for message %s: %s", message.id, exc)
        return None


# Mirrors the agent's own bound (email_agent.MAX_TRANSLATE_CHARS), checked here first so an
# over-long body gets a clear answer instead of a validation error that echoes the body back.
MAX_TRANSLATE_CHARS = 20_000
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


async def translate_email(message_id: str, language: str) -> dict | None:
    """The masked body in another language. Not stored: it is a reading aid, regenerated on ask.

    Only masked text is sent, so this reaches the model with nothing drafting did not already send.
    """
    try:
        pk = UUID(message_id)
    except ValueError:
        return None
    async with get_sessionmaker()() as session:
        message = await session.get(Message, pk)
    if message is None:
        return None
    if not message.is_masked:
        raise TranslationError("masking_pending", 409)
    text = plain_text(message.body_masked or "")
    if len(text) > MAX_TRANSLATE_CHARS:
        raise TranslationError("email_too_long_to_translate", 413)
    try:
        translated = await _call_agent("/translate", {"text": text, "language": language})
    except httpx.HTTPStatusError as exc:
        await audit("translate_email", f"message={message_id} language={language}", success=False)
        raise TranslationError(_agent_error_code(exc.response), exc.response.status_code) from exc
    except httpx.HTTPError as exc:
        raise TranslationError("agent_unreachable", 502) from exc
    await audit("translate_email", f"message={message_id} language={language}")
    return translated


async def refine_email(message_id: str, instruction: str, draft: str) -> DashboardEmail | None:
    """Revise the draft per a user instruction and store it (dashboard's Refine box)."""
    try:
        pk = UUID(message_id)
    except ValueError:
        return None
    async with get_sessionmaker()() as session:
        message = await session.get(Message, pk)
        if message is None:
            return None
        refined = await _refine(message, draft, instruction) if message.is_masked else None
        if refined:
            message.draft_reply = refined
        await audit("refine_draft", f"message={message_id}", success=bool(refined))
        email = _to_email(message)
        await session.commit()
        return email
