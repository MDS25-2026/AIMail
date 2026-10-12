"""Whether an email has an attachment the listener could not read (specs/features/readable-emails.md)."""

from sqlalchemy import select

from app.admin.stats import audit_fields, is_attachment_drop
from app.db.models import AuditLog, Message
from app.db.session import get_sessionmaker

# Written by the listener (listener/ocr.go) when a read fails; a page withheld on purpose is not a failure.
READ_ACTIONS = ("read_attachment", "ocr_attachment")


async def has_unread_attachment(message: Message) -> bool:
    if not message.gmail_message_id:
        return False
    async with get_sessionmaker()() as session:
        rows = (await session.scalars(select(AuditLog).where(
            AuditLog.user_id == message.user_id, AuditLog.action.in_(READ_ACTIONS),
            AuditLog.success.is_(False), AuditLog.detail.contains(message.gmail_message_id)))).all()
    return any(audit_fields(row).get("gmail_message_id") == message.gmail_message_id and not is_attachment_drop(row)
               for row in rows)
