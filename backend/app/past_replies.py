"""Past replies as search items (specs/features/writing-profile.md), stored only while learning is on.

Everything is masked with mask_for_style, so each placeholder becomes "(hidden)": a placeholder
copied from an old reply would otherwise be filled from the new thread's details at send time.
"""

import logging
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ownership import Scope
from app.db.models import DocType, Document
from app.rag.chunk import Piece
from app.rag.ingest import store_chunks
from app.rag.mask import DocumentMaskingError
from app.writing_style import mask_for_style

logger = logging.getLogger(__name__)

# The item is one chunk; the reply keeps its half even under a long email, since it is what gets reused.
PAST_REPLY_MAX_CHARS = 4000
PAST_REPLY_TITLE = "Your earlier reply"
SOURCE_PREFIX = "sent://"
# The draft model reads the item as context; this keeps an old "by Friday" from becoming a new promise.
PAST_REPLY_HEADER = ("An earlier reply to a different email. Reuse how it answers, never its dates, "
                     "figures or promises.")


def past_reply_text(email: str, reply: str) -> str:
    kept_reply = reply.strip()[:PAST_REPLY_MAX_CHARS // 2]
    return f"{PAST_REPLY_HEADER}\n\nThey wrote:\n{email.strip()[:PAST_REPLY_MAX_CHARS - len(kept_reply)]}\n\nYou replied:\n{kept_reply}"


async def remember_reply(user_id: UUID, message_id: UUID, email: str, reply: str) -> None:
    """Stored after the send; the background pass embeds it. A failure is logged, never raised."""
    try:
        masked = await mask_for_style(past_reply_text(email, reply))
        await store_chunks(f"{SOURCE_PREFIX}{message_id}", PAST_REPLY_TITLE, [Piece(masked)],
                           scope=Scope(owner_id=user_id), doc_type=DocType.SENT_REPLY)
    except (DocumentMaskingError, SQLAlchemyError):
        logger.exception("past replies: could not store the reply to message %s", message_id)


async def forget_replies(session: AsyncSession, user_id: UUID) -> None:
    """Chunks and both kinds of vector go with the document (ON DELETE CASCADE)."""
    await session.execute(delete(Document).where(Document.user_id == user_id,
                                                 Document.doc_type == DocType.SENT_REPLY))
