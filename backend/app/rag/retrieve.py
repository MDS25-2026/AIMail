"""Cosine top-k retrieval of policy chunks. This is Lane B's Seam 2 output to Lane C."""

from sqlalchemy import ColumnElement, Select, select

from app.contracts import ContextChunk
from app.core.constants import EMBEDDING_TAG
from app.core.ownership import Scope
from app.db.models import Chunk, Document, Embedding, LocalEmbedding
from app.db.session import get_sessionmaker
from app.private_mode import DraftProvider
from app.rag.embed import embed_query
from app.rag.local_embed import embed_query_locally, local_model, local_tag


async def _gemini_search(masked_email: str, k: int, scope: Scope) -> Select | None:
    query_vector = await embed_query(masked_email)
    if query_vector is None:
        return None
    return _search(Embedding, EMBEDDING_TAG, Embedding.embedding.cosine_distance(query_vector), k, scope)


async def _local_search(masked_email: str, k: int, scope: Scope) -> Select | None:
    # No local embedding model set up: Private mode drafts without search rather than ask Gemini.
    if not local_model():
        return None
    query_vector = await embed_query_locally(masked_email)
    if query_vector is None:
        return None
    distance = LocalEmbedding.embedding.cosine_distance(query_vector)
    return _search(LocalEmbedding, local_tag(), distance, k, scope)


def _search(table: type[Embedding] | type[LocalEmbedding], tag: str, distance: ColumnElement[float], k: int,
            scope: Scope) -> Select:
    return (
        select(Chunk.id, Chunk.content, Document.title, distance.label("distance"))
        .join(table, table.chunk_id == Chunk.id)
        .join(Document, Document.id == Chunk.document_id)
        .where(table.model_name == tag, scope.where(Document.user_id))
        .order_by(distance)
        .limit(k)
    )


async def retrieve(masked_email: str, k: int, *, scope: Scope,
                   provider: DraftProvider = DraftProvider.GEMINI) -> list[ContextChunk]:
    """Return the top-k most similar policy chunks for a masked email.

    The masked email is used directly as the query here (the S3 baseline). Query
    reformulation (R03.1) is a later slice that must beat this number on the eval set. Only the
    scope's own documents can ground a draft, so nothing cites another user's files. In Private
    mode the email is embedded and searched locally only.
    """
    search = _local_search if provider == DraftProvider.LOCAL else _gemini_search
    stmt = await search(masked_email, k, scope)
    if stmt is None:
        return []
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
