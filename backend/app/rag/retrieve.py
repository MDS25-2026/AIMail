"""Cosine top-k retrieval of policy chunks. This is Lane B's Seam 2 output to Lane C."""

from sqlalchemy import select

from app.contracts import ContextChunk
from app.core.constants import EMBEDDING_TAG
from app.core.ownership import Scope
from app.db.models import Chunk, Document, Embedding
from app.db.session import get_sessionmaker
from app.rag.embed import embed_query


async def retrieve(masked_email: str, k: int, *, scope: Scope) -> list[ContextChunk]:
    """Return the top-k most similar policy chunks for a masked email.

    The masked email is used directly as the query here (the S3 baseline). Query
    reformulation (R03.1) is a later slice that must beat this number on the eval set. Only the
    scope's own documents can ground a draft, so nothing cites another user's files.
    """
    query_vector = await embed_query(masked_email)
    if query_vector is None:
        return []
    distance = Embedding.embedding.cosine_distance(query_vector)
    stmt = (
        select(Chunk.id, Chunk.content, Document.title, distance.label("distance"))
        .join(Embedding, Embedding.chunk_id == Chunk.id)
        .join(Document, Document.id == Chunk.document_id)
        .where(Embedding.model_name == EMBEDDING_TAG, scope.where(Document.user_id))
        .order_by(distance)
        .limit(k)
    )
    async with get_sessionmaker()() as session:
        rows = (await session.execute(stmt)).all()
    return [
        ContextChunk(
            chunk_id=row.id,
            content=row.content,
            similarity_score=max(0.0, min(1.0, 1.0 - row.distance)),
            source_title=row.title or "",
        )
        for row in rows
    ]
