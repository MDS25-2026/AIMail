"""The mailbox owner's display name: the sign-off placeholder's value for a reply and a new email."""

from contextlib import nullcontext
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserProfile
from app.db.session import get_sessionmaker


async def owner_name(owner_id: UUID | None, session: AsyncSession | None = None) -> str:
    """In the caller's session when given, so opening an email reads everything through one connection."""
    if owner_id is None:
        return ""
    async with nullcontext(session) if session is not None else get_sessionmaker()() as active:
        return await active.scalar(select(UserProfile.display_name).where(UserProfile.id == owner_id)) or ""
