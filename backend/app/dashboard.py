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

from app.audit import audit
from app.contracts import DashboardEmail, priority_label
from app.core.config import get_settings
from app.db.models import Message
from app.db.session import get_sessionmaker
from app.gmail_send import SendError, send_reply
from app.rag.embed import EmbeddingError
from app.rag.retrieve import retrieve
from app.rag.utils import format_rag_context

logger = logging.getLogger(__name__)


def _to_email(message: Message) -> DashboardEmail:
    return DashboardEmail(
        id=str(message.id),
        sender=message.from_addr or "",
        subject=message.subject or "",
        preview=message.snippet_masked or "",
        body=message.body_masked or "",
        timestamp=(message.received_at or message.created_at).isoformat(),
        priority=priority_label(message.importance),
        threadContext=[],
        aiSummary=message.ai_summary or "",
        actionItems=message.action_items or [],
        draftReply=message.draft_reply or "",
        tone="professional",
        sources=[],
        piiMasked=bool((message.emails_masked or 0) + (message.phones_masked or 0)),
        criticConfidence=message.critic_confidence or 0.0,
        sentAt=message.sent_at.isoformat() if message.sent_at else None,
        isRead=message.read_at is not None,
    )


async def list_dashboard_emails(limit: int = 50) -> list[DashboardEmail]:
    stmt = select(Message).order_by(Message.created_at.desc()).limit(limit)
    async with get_sessionmaker()() as session:
        rows = (await session.scalars(stmt)).all()
    return [_to_email(message) for message in rows]


async def generate_pending(limit: int | None = None) -> int:
    """Generate + cache drafts for messages without one; return how many were generated.

    Shared by the `make generate` script (no limit) and the background poller (small batch, to stay
    under Gemini's free-tier rate limit). Commits per message to keep progress on a mid-run failure.
    """
    generated = 0
    async with get_sessionmaker()() as session:
        stmt = select(Message).where(Message.generated_at.is_(None))
        if limit is not None:
            stmt = stmt.limit(limit)
        pending = (await session.scalars(stmt)).all()
        for message in pending:
            if await _generate_and_store(message):
                generated += 1
            await session.commit()
    return generated


_TONE_PROMPTS = {
    "professional": "professional, concise, and collaborative",
    "casual": "casual, warm, and friendly",
}


async def _generate(message: Message, tone: str = "professional") -> dict:
    """Retrieve policy context (Lane B) and call Lane C's /process-email. Returns {} on any failure."""
    try:
        chunks = await retrieve(message.body_masked or "", k=5)
        payload = {
            "thread_context": "",
            "email_body": message.body_masked or "",
            "rag_context": format_rag_context(chunks),
            "tone": _TONE_PROMPTS.get(tone, _TONE_PROMPTS["professional"]),
        }
        url = get_settings().email_agent_url.rstrip("/") + "/process-email"
        # Lane C runs a multi-step pipeline; keep a generous timeout so a slow run isn't dropped.
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, EmbeddingError, ValueError) as exc:
        logger.warning("draft generation failed for message %s: %s", message.id, exc)
        return {}


async def _generate_and_store(message: Message, tone: str = "professional") -> bool:
    """Generate the Lane C draft and cache it on the message; return True if a draft was stored.

    Caches a real draft, and also an "NA" result (the agent decided no reply is needed, e.g. a
    notification) so the poller stops retrying it. A non-NA empty draft is a transient failure and
    left uncached to retry. The caller owns committing the session.
    """
    generated = await _generate(message, tone)
    if not generated:  # {} means the call failed (rate limit / error) — leave uncached to retry
        return False
    draft = generated.get("draft") or ""
    if not draft and generated.get("category") != "NA":
        return False
    message.ai_summary = generated.get("summary") or ""
    message.draft_reply = draft
    message.action_items = generated.get("action_items") or []
    message.critic_confidence = float(generated.get("confidence") or 0.0)
    message.generated_at = datetime.now(timezone.utc)
    await audit(
        "generate_draft",
        f"message={message.id} tone={tone} confidence={message.critic_confidence:.2f}",
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
        if message.generated_at is None:
            await _generate_and_store(message)
        # Opening the detail view is the moment a person actually reads it. Set once so the
        # first-open time is preserved rather than being bumped on every revisit.
        if message.read_at is None:
            message.read_at = datetime.now(timezone.utc)
        email = _to_email(message)
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
        await _generate_and_store(message, tone)
        email = _to_email(message)
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
                await send_reply(message.from_addr or "", message.subject or "", draft)
            except SendError:
                # The failed attempt is the row an auditor most wants; log before unwinding.
                await audit("approve_and_send", f"message={message_id}", success=False)
                raise
            message.draft_reply = draft
            message.sent_at = datetime.now(timezone.utc)
            await audit("approve_and_send", f"message={message_id}")
        email = _to_email(message)
        await session.commit()
        return email


async def _refine(message: Message, draft: str, instruction: str) -> str | None:
    """Call Lane C's /refine to revise a draft per a user instruction. None on failure."""
    try:
        payload = {"email_body": message.body_masked or "", "draft": draft, "instruction": instruction}
        url = get_settings().email_agent_url.rstrip("/") + "/refine"
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json().get("draft")
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("refine failed for message %s: %s", message.id, exc)
        return None


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
        refined = await _refine(message, draft, instruction)
        if refined:
            message.draft_reply = refined
        await audit("refine_draft", f"message={message_id}", success=bool(refined))
        email = _to_email(message)
        await session.commit()
        return email
