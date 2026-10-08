"""Cosine top-k retrieval of policy chunks. This is Lane B's Seam 2 output to Lane C."""

from sqlalchemy import ColumnElement, Select, select

import model_gateway
from app.contracts import ContextChunk
from app.core.constants import EMBEDDING_TAG
from app.core.ownership import Scope
from app.core.providers import Provider
from app.db.models import Chunk, Document, Embedding, LocalEmbedding
from app.db.session import get_sessionmaker
from app.rag.chunk import SECTION_KEY
from app.rag.local_embed import local_model, local_tag

SECTION_SEPARATOR = " · "
SEARCH = "search"  # the egress purpose of embedding a query
# A hit scoring below this share of the best one is dropped (specs/features/rag-retrieval.md).
# Per model: Gemini's scores sit close together, the local model's spread wider.
RELATIVE_CUTOFF = {Provider.GEMINI: 0.93, Provider.LOCAL: 0.85}


async def _gemini_search(masked_email: str, k: int, scope: Scope) -> Select | None:
    query_vector = await model_gateway.embed_query(masked_email, provider=Provider.GEMINI, purpose=SEARCH)
    if query_vector is None:
        return None
    return _search(Embedding, EMBEDDING_TAG, Embedding.embedding.cosine_distance(query_vector), k, scope)


async def _local_search(masked_email: str, k: int, scope: Scope) -> Select | None:
    # No local embedding model set up: Private mode drafts without search rather than ask Gemini.
    if not local_model():
        return None
    query_vector = await model_gateway.embed_query(masked_email, provider=Provider.LOCAL, purpose=SEARCH)
    if query_vector is None:
        return None
    distance = LocalEmbedding.embedding.cosine_distance(query_vector)
    return _search(LocalEmbedding, local_tag(), distance, k, scope)


def _search(table: type[Embedding] | type[LocalEmbedding], tag: str, distance: ColumnElement[float], k: int,
            scope: Scope) -> Select:
    return (
        select(Chunk.id, Chunk.content, Document.title, Chunk.meta[SECTION_KEY].astext.label("section"),
               distance.label("distance"))
        .join(table, table.chunk_id == Chunk.id)
        .join(Document, Document.id == Chunk.document_id)
        .where(table.model_name == tag, scope.where(Document.user_id))
        .order_by(distance)
        .limit(k)
    )


async def retrieve(masked_email: str, k: int, *, scope: Scope, provider: Provider) -> list[ContextChunk]:
    """Return the top-k most similar policy chunks for a masked email.

    The masked email is used directly as the query here (the S3 baseline). Query
    reformulation (R03.1) is a later slice that must beat this number on the eval set. Only the
    scope's own documents can ground a draft, so nothing cites another user's files. In Private
    mode the email is embedded and searched locally only.
    """
    search = _local_search if provider == Provider.LOCAL else _gemini_search
    stmt = await search(masked_email, k, scope)
    if stmt is None:
        return []
    async with get_sessionmaker()() as session:
        rows = (await session.execute(stmt)).all()
    found = [
        ContextChunk(
            chunk_id=row.id,
            content=row.content,
            similarity_score=max(0.0, min(1.0, 1.0 - row.distance)),
            source_title=_label(row.title, row.section),
        )
        for row in rows
    ]
    return close_to_best(found, RELATIVE_CUTOFF[provider])


def _label(title: str | None, section: str | None) -> str:
    return f"{title or ''}{SECTION_SEPARATOR}{section}" if section else title or ""


def close_to_best(found: list[ContextChunk], cutoff: float) -> list[ContextChunk]:
    """Hits within reach of the best one; rows arrive best first."""
    if not found:
        return []
    floor = found[0]["similarity_score"] * cutoff
    return [chunk for chunk in found if chunk["similarity_score"] >= floor]
