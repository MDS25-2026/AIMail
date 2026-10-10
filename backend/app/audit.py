"""The audit trail: what AIMail did, for whom (specs/context/backbone-contracts.md).

Every row names an action from one list and carries structured fields, stored as compact JSON in
`detail`, so the trail is queried and shown without parsing prose. Fields hold ids, codes and counts,
never email content or addresses. The database chains and seals each row (migrations 0024, 0025).

Two ways to write:
- record(session, ...) adds the row to the caller's transaction: the change and its audit row commit or
  roll back together, so the trail can't claim something that did not happen, or miss something that did.
- audit(...) writes in its own session, for failures and for work that has no transaction of its own. A
  failed write there is logged, never raised: losing a row is bad, failing the user's action for it is worse.
"""

import json
import logging
from enum import StrEnum
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog
from app.db.session import get_sessionmaker

logger = logging.getLogger(__name__)

AuditValue = str | int | float | bool | None


class AuditAction(StrEnum):
    GENERATE_DRAFT = "generate_draft"
    REFINE_DRAFT = "refine_draft"
    TRANSLATE_EMAIL = "translate_email"
    APPROVE_AND_SEND = "approve_and_send"
    SEND_OUTCOME_UNKNOWN = "send_outcome_unknown"
    SEND_RECONCILED = "send_reconciled"
    CONFIRM_SENDER = "confirm_sender"
    DOCUMENT_DELETED = "document_deleted"
    DISCONNECT_GMAIL = "disconnect_gmail"
    DELETE_ACCOUNT = "delete_account"
    PRIVATE_MODE = "private_mode"
    SCAN_READING = "scan_reading"
    TEMPLATE_SAVED = "template_saved"
    TEMPLATE_DELETED = "template_deleted"
    TEMPLATE_USED = "template_used"
    SEND_SCHEDULED = "send_scheduled"
    SCHEDULED_SEND_CANCELLED = "scheduled_send_cancelled"
    EMAIL_SNOOZED = "email_snoozed"
    QUIET_HOURS = "quiet_hours"
    TODO_SETTINGS = "todo_settings"
    HOLDING_REPLY_SETTINGS = "holding_reply_settings"
    HOLDING_REPLY_SCHEDULED = "holding_reply_scheduled"
    HOLDING_REPLY_CANCELLED = "holding_reply_cancelled"
    HOLDING_REPLY_SENT = "holding_reply_sent"
    HOLDING_REPLY_OUTCOME_UNKNOWN = "holding_reply_outcome_unknown"
    WRITING_STYLE_DESCRIPTION = "writing_style_description"
    WRITING_STYLE_LEARNING = "writing_style_learning"
    WRITING_STYLE_EXAMPLE_ADDED = "writing_style_example_added"
    WRITING_STYLE_EXAMPLE_DELETED = "writing_style_deleted_example"
    WRITING_STYLE_HABIT_HIDDEN = "writing_style_hid_habit"
    WRITING_STYLE_DELETED = "writing_style_deleted"
    ADMIN_SIGN_IN = "admin_sign_in"


def audit_detail(fields: dict[str, AuditValue | UUID]) -> str:
    """Compact JSON with sorted keys: one canonical text, which the row's hash covers."""
    return json.dumps({key: str(value) if isinstance(value, UUID) else value for key, value in fields.items()},
                      sort_keys=True, separators=(",", ":"))


def audit_row(action: AuditAction, *, user_id: UUID | None, success: bool = True,
              **fields: AuditValue | UUID) -> AuditLog:
    return AuditLog(action=action.value, detail=audit_detail(fields), success=success, user_id=user_id)


def record(session: AsyncSession, action: AuditAction, *, user_id: UUID | None, success: bool = True,
           **fields: AuditValue | UUID) -> None:
    """The row joins the caller's transaction."""
    session.add(audit_row(action, user_id=user_id, success=success, **fields))


async def audit(action: AuditAction, *, user_id: UUID | None = None, success: bool = True,
                **fields: AuditValue | UUID) -> None:
    try:
        async with get_sessionmaker()() as session:
            record(session, action, user_id=user_id, success=success, **fields)
            await session.commit()
    except SQLAlchemyError:
        logger.exception("audit write failed: action=%s user_id=%s", action, user_id)
