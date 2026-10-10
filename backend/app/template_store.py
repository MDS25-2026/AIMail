"""Saved reply templates in the database (specs/features/reply-templates.md). Personal only."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, func, select, update

from app.core.constants import MAX_TEMPLATES
from app.core.errors import DomainError, ErrorCode
from app.core.language import detect_language
from app.db.models import ReplyTemplate
from app.db.session import get_sessionmaker
from app.templates import matching_template_id

# Most recently used first, then most recently edited: the order the list and the suggestion use.
_ORDER = (ReplyTemplate.last_used_at.desc().nulls_last(), ReplyTemplate.updated_at.desc())


async def list_templates(user_id: UUID) -> list[ReplyTemplate]:
    async with get_sessionmaker()() as session:
        return list((await session.scalars(
            select(ReplyTemplate).where(ReplyTemplate.user_id == user_id).order_by(*_ORDER))).all())


async def get_template(user_id: UUID, template_id: UUID) -> ReplyTemplate | None:
    async with get_sessionmaker()() as session:
        return await session.scalar(select(ReplyTemplate).where(
            ReplyTemplate.id == template_id, ReplyTemplate.user_id == user_id))


async def create_template(user_id: UUID, fields: dict) -> ReplyTemplate:
    async with get_sessionmaker()() as session, session.begin():
        count = await session.scalar(select(func.count()).where(ReplyTemplate.user_id == user_id))
        if (count or 0) >= MAX_TEMPLATES:
            raise DomainError(ErrorCode.TOO_MANY_TEMPLATES)
        template = ReplyTemplate(user_id=user_id, **fields)
        session.add(template)
        await session.flush()
        await session.refresh(template)  # the timestamps are set by the database
    return template


async def update_template(user_id: UUID, template_id: UUID, fields: dict) -> ReplyTemplate | None:
    async with get_sessionmaker()() as session, session.begin():
        return await session.scalar(
            update(ReplyTemplate)
            .where(ReplyTemplate.id == template_id, ReplyTemplate.user_id == user_id)
            .values(**fields, updated_at=func.now())
            .returning(ReplyTemplate))


async def delete_template(user_id: UUID, template_id: UUID) -> bool:
    async with get_sessionmaker()() as session, session.begin():
        deleted = await session.scalar(
            delete(ReplyTemplate)
            .where(ReplyTemplate.id == template_id, ReplyTemplate.user_id == user_id)
            .returning(ReplyTemplate.id))
    return deleted is not None


async def mark_used(template_id: UUID) -> None:
    async with get_sessionmaker()() as session, session.begin():
        await session.execute(update(ReplyTemplate).where(ReplyTemplate.id == template_id)
                              .values(last_used_at=datetime.now(timezone.utc)))


async def suggested_template_id(user_id: UUID | None, text: str) -> str | None:
    """The template to offer for an email: same language, a trigger word in it, most recent first."""
    if user_id is None:
        return None
    templates = await list_templates(user_id)
    candidates = [(str(t.id), t.language, t.trigger_keywords or []) for t in templates]
    return matching_template_id(candidates, detect_language(text), text)
