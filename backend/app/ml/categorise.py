"""Classify each email once and store it (messages.category), instead of on every inbox load.

The worker runs this; it also backfills rows stored before it existed. Only emails whose content is
stored are classified: a quarantined one is picked up once the listener can mask it.
"""

import logging

from sqlalchemy import select, update

from app.db.models import MaskingStatus, Message
from app.db.session import get_sessionmaker
from app.ml.category import category_text, is_model_available, predict_category

logger = logging.getLogger(__name__)


async def classify_pending(limit: int) -> int:
    """How many emails were classified. Nothing is stored when the model is missing, so a later
    deploy with the model classifies them properly instead of leaving a fallback in place."""
    if not is_model_available():
        return 0
    async with get_sessionmaker()() as session:
        rows = (await session.execute(
            select(Message.id, Message.subject, Message.body_masked)
            .where(Message.category.is_(None), Message.masking_status == MaskingStatus.COMPLETE,
                   Message.body_masked.is_not(None))
            .order_by(Message.created_at.desc()).limit(limit)
        )).all()
    if not rows:
        return 0
    async with get_sessionmaker()() as session, session.begin():
        for row in rows:
            category, confidence = predict_category(category_text(row.subject, row.body_masked))
            # Only where still empty: two workers never overwrite each other's result.
            await session.execute(update(Message).where(Message.id == row.id, Message.category.is_(None))
                                  .values(category=category.value, category_confidence=confidence))
    return len(rows)
