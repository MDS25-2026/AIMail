"""Keeping the egress records (model_gateway.Egress) of a draft, a refine, a translation or a search.

A failure to keep them is logged and never fails the user's action: the prompt has already gone.
"""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db.models import ModelEgress
from app.db.session import get_sessionmaker

logger = logging.getLogger(__name__)

# The receipt shows the latest drafting run; older rows stay for the record.
RECEIPT_ROWS = 20


def _row(record: dict, user_id: UUID | None, message_id: UUID | None) -> ModelEgress:
    return ModelEgress(user_id=user_id, message_id=message_id, purpose=str(record.get("purpose", "")),
                       provider=str(record.get("provider", "")), chars=int(record.get("chars", 0)),
                       sha256=str(record.get("sha256", "")), hidden=dict(record.get("hidden") or {}),
                       caught=int(record.get("caught", 0)))


async def save_egress(records: list[dict], *, user_id: UUID | None, message_id: UUID | None) -> None:
    if not records:
        return
    try:
        async with get_sessionmaker()() as session, session.begin():
            session.add_all(_row(record, user_id, message_id) for record in records)
    except SQLAlchemyError:
        logger.exception("could not keep %d egress record(s) for message %s", len(records), message_id)


async def egress_for(message_id: UUID) -> list[ModelEgress]:
    async with get_sessionmaker()() as session:
        rows = await session.scalars(select(ModelEgress).where(ModelEgress.message_id == message_id)
                                     .order_by(ModelEgress.created_at.desc()).limit(RECEIPT_ROWS))
        return list(rows)
