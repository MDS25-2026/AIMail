"""Compose: new emails written from a brief and the company's own documents (specs/features/compose.md).

A draft is stored with placeholders. Details the user typed (addresses, phone, IC, passport and card
numbers) are numbered and their values sealed in the draft's own vault, so the AI only ever sees the
placeholders and the send fills them in; typed names are hidden from the model for one request and put
back, as Refine does for a reply. No database connection is held while the agent or Gmail works.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import getaddresses, parseaddr
from enum import StrEnum
from uuid import UUID, uuid4

import httpx
from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app import agent_client, connections
from app.agent_contract import (
    TONE_PROMPTS,
    ComposeRefineRequest,
    ComposeRequest,
    ComposeResponse,
    Tone,
)
from app.audit import AuditAction, audit, record
from app.contracts import (
    ComposeDraftView,
    ComposeList,
    ComposeState,
    ComposeSummary,
    Detail,
    Source,
)
from app.core.errors import DomainError, ErrorCode
from app.core.language import detect_language
from app.core.ownership import Scope
from app.core.redaction import PLACEHOLDER, has_redaction_marker
from app.core.typed_names import TypedNames
from app.core.typed_text import mask_typed_text
from app.core.vault import (
    DetailKind,
    ThreadMap,
    VaultUnavailableError,
    open_vault,
    seal_vault,
)
from app.db.models import ComposeDraft, SentMessage
from app.db.session import get_sessionmaker
from app.draft_storage import (
    egress_view,
    rag_context_of,
    review_columns,
    source_records,
)
from app.egress_log import egress_for_draft, save_egress
from app.gmail_send import SendError, SendOutcomeUnknownError, SentReply, send_new
from app.owner import owner_name
from app.private_mode import model_for
from app.rag.errors import EmbeddingError
from app.rag.mask import DocumentMaskingError
from app.rag.retrieve import retrieve
from app.rag.utils import format_rag_context
from app.review_reasons import review_reasons
from app.templates import has_unfilled_variable
from app.writing_style import style_for
from model_gateway import track_egress

logger = logging.getLogger(__name__)

MAX_BRIEF_CHARS = 4_000
MAX_SUBJECT_CHARS = 300
MAX_ADDRESS_CHARS = 320  # RFC 5321's longest path
MAX_RECIPIENTS = 20  # To and Cc together: a person writing, not a mailing list
MAX_UNSENT_DRAFTS = 200
SENT_LISTED = 50
PREVIEW_CHARS = 140
RETRIEVED_PASSAGES = 5
# Past the slowest send can take (three 30 s Gmail calls, each retried once on a refreshed token), so a
# claim this recent may still be in flight; after it, the outcome is the user's to settle.
SEND_IN_FLIGHT = timedelta(minutes=10)
# Bound into each vault's sealing, so a draft's vault can never open as a received email's.
_VAULT_KEY_PREFIX = "compose:"
# One address: a local part, an @ and a dotted domain, nothing that could end a header.
_ADDRESS = re.compile(r"^[^@\s<>,;\"]+@[^@\s<>,;\"]+\.[^@\s<>,;\"]+$")


class SettleOutcome(StrEnum):
    SENT = "sent"
    NOT_SENT = "not_sent"


@dataclass(frozen=True)
class ComposeFields:
    """What the user typed; None leaves a field as stored."""

    to: list[str] | None = None
    cc: list[str] | None = None
    subject: str | None = None
    brief: str | None = None
    body: str | None = None
    tone: Tone | None = None


@dataclass(frozen=True)
class _Prepared:
    """A draft's text for the model, read in one short session that is closed before the agent is called."""

    brief: str
    subject: str
    body: str
    tone: Tone
    recipients: list[str]
    sign_off: str
    rag_sources: list[dict]
    # What the model's answer is written over: a change since (another tab) refuses it rather than lose that change.
    updated_at: datetime


# ---------- Reading ----------

def state_of(row: ComposeDraft, now: datetime | None = None) -> ComposeState:
    if row.sent_at is not None:
        return ComposeState.SENT
    if row.send_claimed_at is None:
        return ComposeState.DRAFT
    if row.send_claimed_at > (now or datetime.now(timezone.utc)) - SEND_IN_FLIGHT:
        return ComposeState.SENDING
    return ComposeState.OUTCOME_UNKNOWN


def _vault_key(draft_id: UUID) -> str:
    return f"{_VAULT_KEY_PREFIX}{draft_id}"


def _details_to_show(row: ComposeDraft, owner: str) -> ThreadMap:
    """The values to fill in for the owner; a vault that will not open leaves its placeholders showing."""
    values: dict[str, str] = {}
    if row.pii_vault is not None:
        try:
            values = open_vault(row.pii_vault, row.user_id, _vault_key(row.id))
        except VaultUnavailableError as exc:
            logger.warning("compose draft %s: vault did not open: %s", row.id, exc)
    details = ThreadMap.of_draft(values, row.subject, row.brief, row.body)
    details.add_owner(owner)
    return details


def _details_to_change(row: ComposeDraft, owner: str) -> ThreadMap:
    """The values before a change. A vault that will not open would be resealed without them, so it stops here."""
    values: dict[str, str] = {}
    if row.pii_vault is not None:
        try:
            values = open_vault(row.pii_vault, row.user_id, _vault_key(row.id))
        except VaultUnavailableError as exc:
            raise DomainError(ErrorCode.MASKING_UNAVAILABLE, "the draft's details cannot be opened") from exc
    details = ThreadMap.of_draft(values, row.subject, row.brief, row.body)
    details.add_owner(owner)
    return details


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _detail_list(details: ThreadMap) -> list[Detail]:
    return [Detail(**detail) for detail in details.details()]


def _view(row: ComposeDraft, details: ThreadMap, egress: list | None = None) -> ComposeDraftView:
    return ComposeDraftView(
        id=str(row.id), to=list(row.to_addrs or []), cc=list(row.cc_addrs or []), subject=row.subject,
        brief=row.brief, body=row.body, tone=Tone(row.tone), state=state_of(row),
        sources=[Source(**source) for source in row.rag_sources or []],
        criticConfidence=row.critic_confidence, reviewReasons=review_reasons(row.critic_checks),
        details=_detail_list(details), egress=[egress_view(item) for item in egress or []],
        generatedAt=_iso(row.generated_at), updatedAt=_iso(row.updated_at) or "", sentAt=_iso(row.sent_at),
    )


def _summary(row: ComposeDraft, owner: str) -> ComposeSummary:
    details = _details_to_show(row, owner)
    preview = " ".join((row.body or row.brief).split())[:PREVIEW_CHARS]
    return ComposeSummary(id=str(row.id), to=list(row.to_addrs or []), subject=row.subject, preview=preview,
                          state=state_of(row), updatedAt=_iso(row.updated_at) or "", sentAt=_iso(row.sent_at),
                          details=_detail_list(details))


async def _load(session: AsyncSession, user_id: UUID, draft_id: UUID, *, for_update: bool = False) -> ComposeDraft:
    """The user's own draft; anyone else's reads as missing."""
    query = select(ComposeDraft).where(ComposeDraft.id == draft_id, ComposeDraft.user_id == user_id)
    row = await session.scalar(query.with_for_update() if for_update else query)
    if row is None:
        raise DomainError(ErrorCode.NOT_FOUND)
    return row


async def list_drafts(user_id: UUID) -> ComposeList:
    owner = await owner_name(user_id)
    async with get_sessionmaker()() as session:
        drafts = (await session.scalars(
            select(ComposeDraft).where(ComposeDraft.user_id == user_id, ComposeDraft.sent_at.is_(None))
            .order_by(ComposeDraft.updated_at.desc()).limit(MAX_UNSENT_DRAFTS))).all()
        sent = (await session.scalars(
            select(ComposeDraft).where(ComposeDraft.user_id == user_id, ComposeDraft.sent_at.is_not(None))
            .order_by(ComposeDraft.sent_at.desc()).limit(SENT_LISTED))).all()
    return ComposeList(drafts=[_summary(row, owner) for row in drafts], sent=[_summary(row, owner) for row in sent])


async def get_draft(user_id: UUID, draft_id: UUID) -> ComposeDraftView:
    owner = await owner_name(user_id)
    async with get_sessionmaker()() as session:
        row = await _load(session, user_id, draft_id)
    return _view(row, _details_to_show(row, owner), await egress_for_draft(draft_id))


# ---------- Changing ----------

def _addresses(typed: list[str]) -> list[str]:
    """As typed, trimmed and without blanks; checked only when sending, so a half-typed address can be saved."""
    return [address.strip() for address in typed if address.strip()]


def _recipient_names(details: ThreadMap, addresses: list[str]) -> list[str]:
    """Each recipient's display name as a placeholder, so a draft can greet them without the model seeing it."""
    names = (parseaddr(address)[0].strip() for address in addresses)
    return [details.add_detail(DetailKind.PERSON, name) for name in names if name]


def _seal(user_id: UUID, draft_id: UUID, details: ThreadMap) -> bytes | None:
    sealable = details.sealable()
    if not sealable:
        return None
    try:
        return seal_vault(sealable, user_id, _vault_key(draft_id))
    except VaultUnavailableError as exc:
        # Never stored readable: without a key, a draft holding details cannot be kept.
        raise DomainError(ErrorCode.MASKING_UNAVAILABLE, "details cannot be sealed") from exc


def _apply(row: ComposeDraft, fields: ComposeFields, details: ThreadMap) -> None:
    """The typed fields into the row, every detail a placeholder whose value goes into the vault."""
    if fields.to is not None:
        row.to_addrs = _addresses(fields.to)
    if fields.cc is not None:
        row.cc_addrs = _addresses(fields.cc)
    # Before the text, so a recipient's name typed in the body becomes their placeholder.
    _recipient_names(details, [*(row.to_addrs or []), *(row.cc_addrs or [])])
    if fields.subject is not None:
        row.subject = details.tokenise_typed(" ".join(fields.subject.split()))
    if fields.brief is not None:
        row.brief = details.tokenise_typed(fields.brief.strip())
    if fields.body is not None:
        row.body = details.tokenise_typed(fields.body)
    if fields.tone is not None:
        row.tone = fields.tone
    row.pii_vault = _seal(row.user_id, row.id, details)
    row.updated_at = datetime.now(timezone.utc)


def _require_editable(row: ComposeDraft) -> None:
    state = state_of(row)
    if state is ComposeState.SENT:
        raise DomainError(ErrorCode.ALREADY_SENT, f"draft {row.id} was already sent")
    if state is not ComposeState.DRAFT:
        raise DomainError(ErrorCode.SEND_IN_PROGRESS, f"draft {row.id} is being sent or may have been sent")


async def create_draft(user_id: UUID, fields: ComposeFields) -> ComposeDraftView:
    owner = await owner_name(user_id)
    async with get_sessionmaker()() as session, session.begin():
        unsent = await session.scalar(select(func.count()).select_from(ComposeDraft).where(
            ComposeDraft.user_id == user_id, ComposeDraft.sent_at.is_(None)))
        if unsent >= MAX_UNSENT_DRAFTS:
            raise DomainError(ErrorCode.TOO_MANY_DRAFTS, f"at most {MAX_UNSENT_DRAFTS} unsent drafts")
        row = ComposeDraft(id=uuid4(), user_id=user_id, to_addrs=[], cc_addrs=[], subject="", brief="", body="",
                           tone=Tone.PROFESSIONAL)
        details = ThreadMap()
        details.add_owner(owner)
        _apply(row, fields, details)
        session.add(row)
    return _view(row, details)


async def update_draft(user_id: UUID, draft_id: UUID, fields: ComposeFields) -> ComposeDraftView:
    owner = await owner_name(user_id)
    async with get_sessionmaker()() as session, session.begin():
        row = await _load(session, user_id, draft_id, for_update=True)
        _require_editable(row)
        details = _details_to_change(row, owner)
        _apply(row, fields, details)
    return _view(row, details, await egress_for_draft(draft_id))


async def delete_draft(user_id: UUID, draft_id: UUID) -> None:
    async with get_sessionmaker()() as session, session.begin():
        row = await _load(session, user_id, draft_id, for_update=True)
        if state_of(row) in (ComposeState.SENDING, ComposeState.OUTCOME_UNKNOWN):
            # Its outcome is the one record of whether Gmail sent it; it is settled before it goes.
            raise DomainError(ErrorCode.SEND_IN_PROGRESS, f"draft {draft_id} is being sent or may have been sent")
        await session.delete(row)
        record(session, AuditAction.COMPOSE_DELETED, user_id=user_id, draft=str(draft_id),
               was_sent=row.sent_at is not None)


# ---------- Writing and refining ----------

async def _prepare(user_id: UUID, draft_id: UUID, fields: ComposeFields) -> tuple[_Prepared, ThreadMap]:
    """Save what the user typed, and read back what the model needs, in one short transaction."""
    owner = await owner_name(user_id)
    async with get_sessionmaker()() as session, session.begin():
        row = await _load(session, user_id, draft_id, for_update=True)
        _require_editable(row)
        details = _details_to_change(row, owner)
        _apply(row, fields, details)
        prepared = _Prepared(brief=row.brief, subject=row.subject, body=row.body, tone=Tone(row.tone),
                             recipients=_recipient_names(details, list(row.to_addrs or [])),
                             sign_off=details.owner or "", rag_sources=list(row.rag_sources or []),
                             updated_at=row.updated_at)
    return prepared, details


async def _style(user_id: UUID, text: str) -> dict:
    async with get_sessionmaker()() as session:
        style = await style_for(session, user_id, detect_language(text))
    return {"style_hint": style.hint, "style_examples": style.examples}


async def _ask_agent(path: str, request: ComposeRequest | ComposeRefineRequest, user_id: UUID,
                     draft_id: UUID) -> dict:
    """The agent's answer as a dict; a refusal is recorded on the receipt and answered with its code."""
    try:
        answer = await agent_client.call(path, request, ComposeResponse)
    except httpx.HTTPStatusError as exc:
        await save_egress(agent_client.refusal_egress(exc.response), user_id=user_id, message_id=None,
                          compose_draft_id=draft_id)
        if exc.response.status_code == httpx.codes.FORBIDDEN:
            logger.error("agent authentication failed: AGENT_TOKEN is missing or mismatched (HTTP 403)")
            raise DomainError(ErrorCode.AGENT_UNAVAILABLE, "agent authentication failed") from exc
        code = ErrorCode.DRAFT_REFUSED if agent_client.is_content_refusal(exc.response) else ErrorCode.AGENT_UNAVAILABLE
        raise DomainError(code, f"compose {path} failed") from exc
    except (httpx.HTTPError, ValidationError) as exc:
        logger.warning("compose %s failed for draft %s: %s", path, draft_id, exc)
        raise DomainError(ErrorCode.AGENT_UNAVAILABLE, f"compose {path} failed") from exc
    return answer.model_dump()


async def _store_answer(user_id: UUID, draft_id: UUID, prepared: _Prepared, columns: dict) -> ComposeDraftView:
    """Write the answer only over the draft it was written from: a send or an edit made meanwhile wins."""
    owner = await owner_name(user_id)
    async with get_sessionmaker()() as session, session.begin():
        stored = await session.scalar(
            update(ComposeDraft)
            .where(ComposeDraft.id == draft_id, ComposeDraft.user_id == user_id,
                   ComposeDraft.send_claimed_at.is_(None), ComposeDraft.sent_at.is_(None),
                   ComposeDraft.updated_at == prepared.updated_at)
            .values(**columns, updated_at=func.now()).returning(ComposeDraft))
        if stored is None:
            raise DomainError(ErrorCode.CONFLICT, f"draft {draft_id} changed, was sent or was deleted meanwhile")
    return _view(stored, _details_to_show(stored, owner), await egress_for_draft(draft_id))


async def write(user_id: UUID, draft_id: UUID, fields: ComposeFields) -> ComposeDraftView:
    """Write the body (and a subject, if none was typed) from the brief and the user's documents."""
    prepared, details = await _prepare(user_id, draft_id, fields)
    if not prepared.brief.strip():
        raise DomainError(ErrorCode.EMPTY, "write a brief first")
    names = TypedNames()
    searched: list[dict] = []
    egress: list[dict] = []
    try:
        provider = await model_for(user_id)
        # Typed names are hidden for this request; mask_typed_text also cuts link queries for the model only.
        brief = await names.hide(mask_typed_text(prepared.brief))
        subject = await names.hide(mask_typed_text(prepared.subject))
        with track_egress() as searched:
            chunks = await retrieve(brief, k=RETRIEVED_PASSAGES, scope=Scope(owner_id=user_id), provider=provider)
        request = ComposeRequest(brief=brief, subject=subject, recipients=prepared.recipients,
                                 rag_context=format_rag_context(chunks), tone=TONE_PROMPTS[prepared.tone],
                                 sign_off=prepared.sign_off, provider=provider,
                                 **await _style(user_id, prepared.brief))
        answer = await _ask_agent("/compose", request, user_id, draft_id)
        egress = answer.pop("egress", [])
    except DocumentMaskingError as exc:
        raise DomainError(ErrorCode.MASKING_UNAVAILABLE, "names could not be checked") from exc
    except EmbeddingError as exc:
        raise DomainError(ErrorCode.AGENT_UNAVAILABLE, "documents could not be searched") from exc
    finally:
        await save_egress([*searched, *egress], user_id=user_id, message_id=None, compose_draft_id=draft_id)
    written = names.restore_answer(answer)
    # Known details stay placeholders; the model saw no others, so nothing new is numbered here.
    columns = {"body": details.tokenise_known(str(written.get("draft") or "")), "rag_sources": source_records(chunks),
               "generated_at": datetime.now(timezone.utc), **review_columns(written)}
    if not prepared.subject.strip():
        columns["subject"] = details.tokenise_known(" ".join(str(written.get("subject") or "").split()))[:MAX_SUBJECT_CHARS]
    view = await _store_answer(user_id, draft_id, prepared, columns)
    await audit(AuditAction.COMPOSE_WRITTEN, user_id=user_id, draft=str(draft_id), sources=len(chunks),
                review=bool(written.get("needs_human_review")))
    return view


async def refine(user_id: UUID, draft_id: UUID, instruction: str, fields: ComposeFields) -> ComposeDraftView:
    """Revise the body per the user's instruction, with the same checks a written draft gets."""
    if not instruction.strip():
        raise DomainError(ErrorCode.EMPTY, "say what to change")
    prepared, details = await _prepare(user_id, draft_id, fields)
    if not prepared.body.strip():
        raise DomainError(ErrorCode.EMPTY, "there is no draft to refine")
    names = TypedNames()
    egress: list[dict] = []
    try:
        provider = await model_for(user_id)
        # A detail typed in the instruction ("add my number 012-…") must be sendable, so it is numbered too.
        known = details.sealable()
        typed_instruction = details.tokenise_typed(instruction)
        request = ComposeRefineRequest(
            brief=await names.hide(mask_typed_text(prepared.brief)),
            draft=await names.hide(mask_typed_text(prepared.body)),
            instruction=await names.hide(mask_typed_text(typed_instruction)),
            subject=await names.hide(mask_typed_text(prepared.subject)),
            recipients=prepared.recipients, rag_context=rag_context_of(prepared.rag_sources),
            tone=TONE_PROMPTS[prepared.tone], sign_off=prepared.sign_off, provider=provider,
            **await _style(user_id, prepared.brief))
        answer = await _ask_agent("/compose/refine", request, user_id, draft_id)
        egress = answer.pop("egress", [])
    except DocumentMaskingError as exc:
        raise DomainError(ErrorCode.MASKING_UNAVAILABLE, "names could not be checked") from exc
    finally:
        await save_egress(egress, user_id=user_id, message_id=None, compose_draft_id=draft_id)
    revised = names.restore_answer(answer)
    if not str(revised.get("draft") or "").strip():
        raise DomainError(ErrorCode.AGENT_UNAVAILABLE, "the revision came back empty")
    columns = {"body": details.tokenise_known(str(revised["draft"])), **review_columns(revised)}
    if details.sealable() != known:
        # Only when the instruction numbered a new detail: its value must be in the vault for the send.
        columns["pii_vault"] = _seal(user_id, draft_id, details)
    view = await _store_answer(user_id, draft_id, prepared, columns)
    await audit(AuditAction.COMPOSE_REFINED, user_id=user_id, draft=str(draft_id),
                review=bool(revised.get("needs_human_review")))
    return view


# ---------- Sending ----------

def checked_recipients(addresses: list[str]) -> list[str]:
    """Each address parsed as a header would be; anything that is not exactly one address is refused."""
    checked = []
    for address in addresses:
        if "\r" in address or "\n" in address or len(address) > MAX_ADDRESS_CHARS:
            raise DomainError(ErrorCode.INVALID_RECIPIENTS, "an address is malformed")
        parsed = getaddresses([address])
        is_bracketed_once = address.count("<") == address.count(">") <= 1
        if len(parsed) != 1 or not is_bracketed_once or not _ADDRESS.fullmatch(parsed[0][1]):
            raise DomainError(ErrorCode.INVALID_RECIPIENTS, "an address is malformed")
        checked.append(address)
    return checked


@dataclass(frozen=True)
class _Outgoing:
    to: list[str]
    cc: list[str]
    subject: str
    body: str
    restored: int


def _outgoing(row: ComposeDraft, details: ThreadMap) -> _Outgoing:
    """The email as the recipient reads it. Raises before anything is claimed if it cannot go as is."""
    to, cc = checked_recipients(list(row.to_addrs or [])), checked_recipients(list(row.cc_addrs or []))
    if not to:
        raise DomainError(ErrorCode.NO_RECIPIENTS, "add a recipient")
    if len(to) + len(cc) > MAX_RECIPIENTS:
        raise DomainError(ErrorCode.INVALID_RECIPIENTS, f"at most {MAX_RECIPIENTS} recipients")
    if not row.subject.strip():
        raise DomainError(ErrorCode.NO_SUBJECT, "add a subject")
    if not row.body.strip():
        raise DomainError(ErrorCode.EMPTY, "the email is empty")
    subject, unresolved_subject = details.restore(row.subject)
    body, unresolved_body = details.restore(row.body)
    if unresolved_subject or unresolved_body or has_unfilled_variable(body):
        raise DomainError(ErrorCode.UNRESOLVED_PLACEHOLDERS, "a placeholder cannot be filled in")
    if has_redaction_marker(subject) or has_redaction_marker(body):
        raise DomainError(ErrorCode.REDACTION_MARKERS, "a redaction marker is left in")
    restored = len(PLACEHOLDER.findall(row.subject)) + len(PLACEHOLDER.findall(row.body))
    return _Outgoing(to=to, cc=cc, subject=subject, body=body, restored=restored)


_Claimed = tuple[ComposeDraft, ThreadMap, _Outgoing]


async def _claim(user_id: UUID, draft_id: UUID, fields: ComposeFields) -> _Claimed | ComposeDraftView:
    """Save the approved fields and claim the send in one transaction; a draft already sent answers its view."""
    owner = await owner_name(user_id)
    # Before the row is locked: it needs a connection of its own.
    can_send = await connections.can_send(user_id)
    async with get_sessionmaker()() as session, session.begin():
        row = await _load(session, user_id, draft_id, for_update=True)
        if row.sent_at is not None:
            return _view(row, _details_to_show(row, owner))
        _require_editable(row)
        details = _details_to_change(row, owner)
        _apply(row, fields, details)
        outgoing = _outgoing(row, details)
        if not can_send:
            raise DomainError(ErrorCode.SEND_NOT_GRANTED, "Gmail send was not granted")
        # Claim-then-send, with the outcome unknown until recorded: a crash in between never reads as unsent.
        now = datetime.now(timezone.utc)
        row.send_claimed_at = now
        row.send_outcome_unknown_at = now
    return row, details, outgoing


async def send(user_id: UUID, draft_id: UUID, fields: ComposeFields, *, remind: bool | None) -> ComposeDraftView:
    """Send the approved email once, from the user's Gmail, as a new thread; then record it."""
    claimed = await _claim(user_id, draft_id, fields)
    if isinstance(claimed, ComposeDraftView):
        return claimed  # sent before this request: answering is idempotent
    row, details, outgoing = claimed
    try:
        sent = await send_new(outgoing.to, outgoing.cc, outgoing.subject, outgoing.body, owner_id=user_id)
    except SendOutcomeUnknownError:
        # The claim stays: Gmail may have sent it, and releasing it would invite a second copy. The request is
        # over, though, so nothing is in flight and the user can settle it now rather than wait out the window.
        await _end_in_flight(user_id, draft_id)
        await audit(AuditAction.COMPOSE_SEND_OUTCOME_UNKNOWN, user_id=user_id, success=False, draft=str(draft_id))
        raise
    except SendError:
        await _release(user_id, draft_id)
        await audit(AuditAction.COMPOSE_SENT, user_id=user_id, success=False, draft=str(draft_id))
        raise
    try:
        stored = await _record(row, outgoing, sent, remind)
    except SQLAlchemyError:
        # Sent, but not recorded: the claim and its unknown mark stay, so it is never sent twice.
        logger.exception("compose draft %s was sent (Gmail id %s) but its record was not saved", draft_id, sent.gmail_id)
        await audit(AuditAction.COMPOSE_SENT, user_id=user_id, draft=str(draft_id), recorded=False,
                    gmail_message=sent.gmail_id)
        row.sent_at = datetime.now(timezone.utc)
        return _view(row, details)
    return _view(stored, details, await egress_for_draft(draft_id))


async def _end_in_flight(user_id: UUID, draft_id: UUID) -> None:
    """Gmail's answer was lost and the request is over: the claim reads as unknown from now on."""
    async with get_sessionmaker()() as session, session.begin():
        await session.execute(update(ComposeDraft).where(ComposeDraft.id == draft_id, ComposeDraft.user_id == user_id)
                              .values(send_claimed_at=func.now() - SEND_IN_FLIGHT))


async def _release(user_id: UUID, draft_id: UUID) -> None:
    """Gmail refused before sending: the draft can be approved again."""
    async with get_sessionmaker()() as session, session.begin():
        await session.execute(update(ComposeDraft).where(ComposeDraft.id == draft_id, ComposeDraft.user_id == user_id)
                              .values(send_claimed_at=None, send_outcome_unknown_at=None))


async def _record(row: ComposeDraft, outgoing: _Outgoing, sent: SentReply, remind: bool | None) -> ComposeDraft:
    """What was sent, its audit row and its waiting-list entry, in one transaction."""
    async with get_sessionmaker()() as session, session.begin():
        stored = await session.scalar(
            update(ComposeDraft).where(ComposeDraft.id == row.id)
            .values(sent_at=func.now(), sent_gmail_id=sent.gmail_id, sent_thread_id=sent.thread_id,
                    send_outcome_unknown_at=None, updated_at=func.now())
            .returning(ComposeDraft))
        record(session, AuditAction.COMPOSE_SENT, user_id=row.user_id, draft=str(row.id), to=len(outgoing.to),
               cc=len(outgoing.cc), restored=outgoing.restored)
        if sent.gmail_id:
            # For the to-do's waiting list; the listener's Sent watch sees the same send and is ignored.
            await session.execute(insert(SentMessage).values(
                user_id=row.user_id, gmail_id=sent.gmail_id, message_id=None, thread_id=sent.thread_id,
                sent_at=func.now(), subject=row.subject, body_masked=row.body, remind=remind,
            ).on_conflict_do_update(index_elements=["gmail_id"], set_={
                "remind": remind, "body_masked": row.body, "subject": row.subject}))
    return stored


async def settle(user_id: UUID, draft_id: UUID, outcome: SettleOutcome) -> ComposeDraftView:
    """The user looked in Gmail's Sent folder: sent stays sent, not sent can be approved again."""
    owner = await owner_name(user_id)
    async with get_sessionmaker()() as session, session.begin():
        row = await _load(session, user_id, draft_id, for_update=True)
        if state_of(row) is not ComposeState.OUTCOME_UNKNOWN:
            raise DomainError(ErrorCode.CONFLICT, f"draft {draft_id} has no outcome to settle")
        if outcome is SettleOutcome.SENT:
            row.sent_at = datetime.now(timezone.utc)
        else:
            row.send_claimed_at = None
        row.send_outcome_unknown_at = None
        row.updated_at = datetime.now(timezone.utc)
        record(session, AuditAction.COMPOSE_OUTCOME_SETTLED, user_id=user_id, draft=str(draft_id), outcome=outcome)
    return _view(row, _details_to_show(row, owner), await egress_for_draft(draft_id))
