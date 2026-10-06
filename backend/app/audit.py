"""Audit trail for Lane B/C actions (audit finding 2.4: backend logging gap).

The Go listener already records ingestion; without this, everything after it — draft
generation, refinement, and the human approval that actually sends mail — left no trace, so
"a human approved this send" was a claim with no evidence behind it.

Two deliberate choices:

- Writes go through their own session, not the caller's. A send that fails must still leave a
  row, and a failed audit write must never poison the transaction doing the real work.
- A failed write is logged and swallowed rather than raised. Losing an audit row is bad;
  failing a user's send because the trail could not be written is worse. This mirrors the
  listener's never-block philosophy.

`detail` must stay free of email content: rows are queried and shown during demos, and the
whole point of the pipeline is that unmasked content does not spread. Message IDs only.
"""

import logging

from sqlalchemy.exc import SQLAlchemyError

from app.db.models import AuditLog
from app.db.session import get_sessionmaker

logger = logging.getLogger(__name__)


async def audit(action: str, detail: str, *, success: bool = True) -> None:
    try:
        async with get_sessionmaker()() as session:
            session.add(AuditLog(action=action, detail=detail, success=success))
            await session.commit()
    except SQLAlchemyError:
        logger.exception("audit write failed: action=%s detail=%s", action, detail)
