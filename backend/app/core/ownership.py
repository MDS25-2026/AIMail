"""Whose mail and documents a caller may touch (specs/features/per-user-mailboxes.md).

Every email and document query filters through a Scope, so the rule lives in one place. Every row
belongs to a connected user; a row with no owner is visible only to a script holding the shared token.
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import ColumnElement, false, select, true
from sqlalchemy.orm import InstrumentedAttribute

from app.db.models import MailboxConnection, UserProfile
from app.db.session import get_sessionmaker


@dataclass(frozen=True)
class Scope:
    """One owner's rows, or every row (EVERYTHING) for scripts and background work."""

    owner_id: UUID | None
    is_everything: bool = False

    def where(self, column: InstrumentedAttribute) -> ColumnElement[bool]:
        if self.is_everything:
            return true()
        # Never "IS NULL": rows with no owner belonged to the retired token.json mailbox, and no user owns them now.
        if self.owner_id is None:
            return false()
        return column == self.owner_id


# Scripts holding the shared token, and background work that already picked a row.
EVERYTHING = Scope(owner_id=None, is_everything=True)


async def is_connected(user_id: UUID) -> bool:
    async with get_sessionmaker()() as session:
        found = await session.scalar(
            select(MailboxConnection.user_id).where(MailboxConnection.user_id == user_id)
        )
    return found is not None


async def scope_for(user_id: UUID | None) -> Scope | None:
    """A signed-in user's scope once their Gmail is connected; None until then."""
    if user_id is not None and await is_connected(user_id):
        return Scope(owner_id=user_id)
    return None


async def scope_of_email(email: str) -> Scope:
    """An account's scope by its sign-in email, for scripts that file rows under someone (make ingest OWNER=)."""
    async with get_sessionmaker()() as session:
        user_id = await session.scalar(select(UserProfile.id).where(UserProfile.email == email.strip().lower()))
    if user_id is None:
        raise LookupError(f"no AIMail account has signed in as {email!r}")
    return Scope(owner_id=user_id)
