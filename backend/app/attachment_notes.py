"""Whether an email has an attachment the listener could not read (specs/features/readable-emails.md)."""

from contextlib import nullcontext

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.stats import audit_fields, is_attachment_drop
from app.db.models import AuditLog, Message
from app.db.session import get_sessionmaker

# Written by the listener (listener/ocr.go) when a read fails; a page withheld on purpose is not a failure.
READ_ACTIONS = ("read_attachment", "ocr_attachment")


async def has_unread_attachment(message: Message, session: AsyncSession | None = None) -> bool:
    if not message.gmail_message_id:
        return False
    async with nullcontext(session) if session is not None else get_sessionmaker()() as active:
        rows = (await active.scalars(select(AuditLog).where(
            AuditLog.user_id == message.user_id, AuditLog.action.in_(READ_ACTIONS),
            AuditLog.success.is_(False), AuditLog.detail.contains(message.gmail_message_id)))).all()
    return any(audit_fields(row).get("gmail_message_id") == message.gmail_message_id and not is_attachment_drop(row)
               for row in rows)
