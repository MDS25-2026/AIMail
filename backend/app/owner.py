"""The mailbox owner's display name: the sign-off placeholder's value for a reply and a new email."""

from uuid import UUID

from sqlalchemy import select

from app.db.models import UserProfile
from app.db.session import get_sessionmaker


async def owner_name(owner_id: UUID | None) -> str:
    if owner_id is None:
        return ""
    async with get_sessionmaker()() as session:
        return await session.scalar(select(UserProfile.display_name).where(UserProfile.id == owner_id)) or ""
