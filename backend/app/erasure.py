"""What is erased for whom, in one place (PDPA right to erasure; specs/features/per-user-mailboxes.md).

Two subjects. Disconnecting a mailbox erases everything AIMail stored *from* it: the mail, what was learned
from the replies sent through it (past replies, style examples taken from sends, learned habits) and the
holding replies sent from it. Deleting the account erases everything the user has, mailbox included.

Every table with a user_id is listed here, either erased or retained with its reason; a test walks the
schema and fails when a new owned table is in neither list, so a feature cannot add data erasure misses.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from sqlalchemy import ColumnElement, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    DocType,
    Document,
    HoldingReply,
    HoldingReplySettings,
    KeywordRule,
    MailboxConnection,
    Message,
    ModelEgress,
    ReplyTemplate,
    SenderRule,
    StyleExample,
    StyleHabit,
    UserPreferences,
    UserProfile,
    WritingStyle,
)
from app.writing_style import ExampleSource


class Subject(StrEnum):
    MAILBOX = "mailbox"  # disconnect Gmail
    ACCOUNT = "account"  # delete the account


@dataclass(frozen=True)
class Rule:
    table: type
    which: Callable[[UUID], ColumnElement[bool]]


# In order: rows that point at others go first, so nothing depends on the database cascading for us.
_FROM_THE_MAILBOX: tuple[Rule, ...] = (
    Rule(HoldingReply, lambda user: HoldingReply.user_id == user),
    Rule(ModelEgress, lambda user: ModelEgress.user_id == user),
    Rule(Message, lambda user: Message.user_id == user),
    Rule(Document, lambda user: (Document.user_id == user) & (Document.doc_type == DocType.SENT_REPLY)),
    Rule(StyleExample, lambda user: (StyleExample.user_id == user) & (StyleExample.source == ExampleSource.SENT)),
    Rule(StyleHabit, lambda user: StyleHabit.user_id == user),  # learned from sends through this mailbox
    Rule(MailboxConnection, lambda user: MailboxConnection.user_id == user),
)
_THE_REST_OF_THE_ACCOUNT: tuple[Rule, ...] = (
    Rule(Document, lambda user: Document.user_id == user),
    Rule(StyleExample, lambda user: StyleExample.user_id == user),
    Rule(WritingStyle, lambda user: WritingStyle.user_id == user),
    Rule(ReplyTemplate, lambda user: ReplyTemplate.user_id == user),
    Rule(HoldingReplySettings, lambda user: HoldingReplySettings.user_id == user),
    Rule(KeywordRule, lambda user: KeywordRule.user_id == user),
    Rule(SenderRule, lambda user: SenderRule.user_id == user),
    Rule(UserPreferences, lambda user: UserPreferences.user_id == user),
    Rule(UserProfile, lambda user: UserProfile.id == user),
)
RULES: dict[Subject, tuple[Rule, ...]] = {
    Subject.MAILBOX: _FROM_THE_MAILBOX,
    Subject.ACCOUNT: _FROM_THE_MAILBOX + _THE_REST_OF_THE_ACCOUNT,
}

# Owned tables deliberately kept, and why.
RETAINED: dict[str, str] = {
    "audit_log": "append-only ledger (migration 0025): rows keep an opaque user id and no personal content",
}


async def erase(session: AsyncSession, user_id: UUID, subject: Subject) -> dict[str, int]:
    """Rows removed per table, within the caller's transaction."""
    counts: dict[str, int] = {}
    for rule in RULES[subject]:
        result = await session.execute(delete(rule.table).where(rule.which(user_id)))
        name = rule.table.__tablename__
        counts[name] = counts.get(name, 0) + (result.rowcount or 0)
    return counts
