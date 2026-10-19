"""Normalise each stored email once (specs/features/normalisation-v2.md, stage 2).

Its language, an English copy of a non-English one (the subject and the sender's own text, from the masked
text only, by the model the owner chose), and the earliest deadline it sets. Every later step reads the
English copy when there is one. Run by the worker; it also covers emails stored before it existed.
"""

import logging

import httpx
from pydantic import ValidationError
from sqlalchemy import select, update

from app import agent_client
from app.agent_contract import MAX_TRANSLATE_CHARS, TranslateRequest, TranslateResponse
from app.core.language import Language, detect_language
from app.core.providers import Provider
from app.db.models import MaskingStatus, Message
from app.db.session import get_sessionmaker
from app.egress_log import save_egress
from app.normalise.deadlines import deadline_in
from app.normalise.quotes import own_text
from app.plain_text import plain_text
from app.private_mode import is_offered, provider_for
from app.quiet_hours import company_default, settings_for

logger = logging.getLogger(__name__)

# The agent's "this will fail the same way every time" status: an unfaithful or oversized translation.
REFUSED = 422


class _TryAgainLater(Exception):
    """The agent could not be reached or failed for now; the email stays in the queue."""


async def normalise_pending(limit: int) -> int:
    """How many emails were normalised this pass."""
    async with get_sessionmaker()() as session:
        rows = (await session.scalars(
            select(Message).where(Message.language.is_(None), Message.masking_status == MaskingStatus.COMPLETE,
                                  Message.body_masked.is_not(None))
            .order_by(Message.created_at.asc()).limit(limit))).all()
    done = 0
    for message in rows:
        try:
            await _normalise(message)
        except _TryAgainLater as exc:
            logger.warning("email %s not normalised yet: %s", message.id, exc)
            if isinstance(exc.__cause__, (httpx.ConnectError, httpx.ConnectTimeout)):
                return done
            continue
        done += 1
    return done


async def _normalise(message: Message) -> None:
    own = own_text(plain_text(message.body_masked or ""))
    language = detect_language(f"{message.subject or ''}\n{own}")
    subject_en, own_en = (None, None) if language == Language.EN else await _english(message, own)
    zone = await _zone_of(message)
    sent = message.received_at or message.created_at
    deadline = deadline_in(own_en or own, sent, zone) if sent else None
    async with get_sessionmaker()() as session, session.begin():
        # Only while still pending: two workers never overwrite each other.
        await session.execute(update(Message).where(Message.id == message.id, Message.language.is_(None)).values(
            language=language.value, subject_en=subject_en, own_text_en=own_en,
            deadline_at=deadline or Message.deadline_at))


async def _english(message: Message, own: str) -> tuple[str | None, str | None]:
    """The English copy, or none when this server has no model the owner allows or it was refused."""
    provider = await provider_for(message.user_id)
    if provider == Provider.LOCAL and not is_offered():
        return None, None
    try:
        subject = await _translated(message, _within_limit(message.subject), provider) if message.subject else None
        return subject, await _translated(message, _within_limit(own), provider)
    except httpx.HTTPStatusError as exc:
        await save_egress(agent_client.refusal_egress(exc.response), user_id=message.user_id, message_id=message.id)
        if exc.response.status_code == 504:
            logger.warning("email %s translation timed out (504): skipping English translation", message.id)
            return None, None
        if not agent_client.is_content_refusal(exc.response):
            raise _TryAgainLater from exc
        return None, None
    except (httpx.HTTPError, ValidationError) as exc:
        raise _TryAgainLater from exc


async def _translated(message: Message, text: str, provider: Provider) -> str:
    answer = await agent_client.call("/translate", TranslateRequest(
        text=text, language=Language.EN.value, provider=provider), TranslateResponse)
    await save_egress(answer.egress, user_id=message.user_id, message_id=message.id)
    return answer.text


def _within_limit(text: str) -> str:
    """The agent's limit, cut at the last paragraph that fits so no sentence is halved."""
    if len(text) <= MAX_TRANSLATE_CHARS:
        return text
    cut = text.rfind("\n\n", 0, MAX_TRANSLATE_CHARS)
    return text[:cut if cut > 0 else MAX_TRANSLATE_CHARS]


async def _zone_of(message: Message) -> str:
    hours = (await settings_for(message.user_id)).effective if message.user_id else await company_default()
    return hours.timezone
