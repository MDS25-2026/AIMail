"""Whose mail and documents a caller may touch (specs/features/per-user-mailboxes.md).

Every email and document query filters through a Scope, so the rule lives in one place. Rows with
no owner (user_id NULL) are the single mailbox from before per-user mailboxes; they belong to that
mailbox's owner (app/core/mailbox.py) until that account connects, which hands them over.
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import ColumnElement, select, true
from sqlalchemy.orm import InstrumentedAttribute

from app.core import mailbox
from app.db.models import MailboxConnection
from app.db.session import get_sessionmaker


@dataclass(frozen=True)
class Scope:
    """One owner's rows. owner_id None means the unowned rows of the original single mailbox."""

    owner_id: UUID | None
    is_everything: bool = False

    def where(self, column: InstrumentedAttribute) -> ColumnElement[bool]:
        if self.is_everything:
            return true()
        if self.owner_id is None:
            return column.is_(None)
        return column == self.owner_id

    def owner_of_new_rows(self) -> "Scope":
        """Who a new row belongs to; a script's writes go to the original unowned mailbox."""
        return LEGACY if self.is_everything else self


# Scripts holding the shared token, and background work that already picked a row.
EVERYTHING = Scope(owner_id=None, is_everything=True)
LEGACY = Scope(owner_id=None)


async def is_connected(user_id: UUID) -> bool:
    async with get_sessionmaker()() as session:
        found = await session.scalar(
            select(MailboxConnection.user_id).where(MailboxConnection.user_id == user_id)
        )
    return found is not None


async def scope_for(user_id: UUID | None, email: str) -> Scope | None:
    """A signed-in user's scope: their connected Gmail, else the unowned mailbox if it is theirs."""
    if user_id is not None and await is_connected(user_id):
        return Scope(owner_id=user_id)
    owner = mailbox.owner()
    if owner and email.lower() == owner:
        return LEGACY
    return None
