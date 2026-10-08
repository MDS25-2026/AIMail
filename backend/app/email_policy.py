"""What an email may do, decided in one place (specs/context/backbone-contracts.md).

Every entry point asks refusal_for(message, action) instead of re-checking the rules itself, and the
background drafter's query is built from the same rules (drafting_filter), so a new rule, or a new
action, is added once. The dashboard mirrors these rules in lib/draftAvailability.ts.
"""

from enum import StrEnum

from sqlalchemy import ColumnElement, and_

from app.core.errors import ErrorCode
from app.db.models import AuthStatus, MaskingStatus, Message


class Action(StrEnum):
    DRAFT = "draft"  # the first draft, on open or by the background drafter
    REDRAFT = "redraft"  # Regenerate, or a tone change
    REFINE = "refine"
    SEND = "send"
    TRANSLATE = "translate"  # a reading aid: drafts nothing, sends nothing


# A sent email's draft is the record of what went out. Send is left out: a repeat send is answered
# with the email as it is, by the send claim, not refused.
_REPLACES_THE_DRAFT = frozenset({Action.DRAFT, Action.REDRAFT, Action.REFINE})
# A spoofer gets nothing written for them; reading their email in another language is still allowed.
_WRITES_TO_THE_SENDER = frozenset({Action.DRAFT, Action.REDRAFT, Action.REFINE, Action.SEND})


def refusal_for(message: Message, action: Action) -> ErrorCode | None:
    """None when allowed; otherwise the code the caller is refused with. Checked in this order everywhere."""
    if action in _REPLACES_THE_DRAFT and message.sent_at is not None:
        return ErrorCode.ALREADY_SENT
    if not message.is_masked:
        return ErrorCode.MASKING_PENDING
    if action in _WRITES_TO_THE_SENDER and message.is_spoofed:
        return ErrorCode.SENDER_UNVERIFIED
    return None


def drafting_filter() -> ColumnElement[bool]:
    """The rows refusal_for allows Action.DRAFT on, as SQL, for the background drafter."""
    return and_(
        Message.sent_at.is_(None),
        Message.masking_status == MaskingStatus.COMPLETE,
        Message.auth_status.is_distinct_from(AuthStatus.SPOOF_DETECTED),
    )
