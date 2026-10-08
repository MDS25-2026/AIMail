"""Empties personal-detail vaults once a reply is unlikely to still be written (restorable masking).

A vault is kept VAULT_RETENTION_DAYS after the email arrived, or SENT_RETENTION_DAYS after its reply
went out, whichever comes first. After that the email shows its placeholders and the original is
read in Gmail.
"""

import logging
from datetime import timedelta

from sqlalchemy import ColumnElement, func, or_, update

from app.core.config import get_settings
from app.db.models import Message
from app.db.session import get_sessionmaker

logger = logging.getLogger(__name__)

SENT_RETENTION_DAYS = 7
RUN_EVERY = timedelta(days=1)


def expired(retention_days: int) -> ColumnElement[bool]:
    now = func.now()
    return Message.pii_vault.is_not(None) & or_(
        Message.created_at < now - timedelta(days=retention_days),
        Message.sent_at < now - timedelta(days=SENT_RETENTION_DAYS),
    )


async def expire_vaults() -> int:
    async with get_sessionmaker()() as session:
        result = await session.execute(
            update(Message).where(expired(get_settings().vault_retention_days)).values(pii_vault=None)
        )
        await session.commit()
    return result.rowcount
