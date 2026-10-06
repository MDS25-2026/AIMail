"""Ingest a policy PDF: extract, chunk, store, embed. Idempotent per source."""

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import EMBEDDING_MODEL
from app.db.models import Chunk, Document, Embedding
from app.db.session import get_sessionmaker
from app.rag.chunk import chunk_text, estimate_tokens, extract_pdf_text
from app.rag.embed import embed_texts

EMBED_BATCH = 100


async def ingest_pdf(path: Path, *, title: str | None = None, doc_type: str = "policy") -> int:
    """Ingest one PDF. Re-ingesting the same path replaces its chunks. Returns chunk count."""
    return await ingest_text(str(path), title or path.stem, extract_pdf_text(path), doc_type=doc_type)


async def ingest_text(source: str, title: str, text: str, *, doc_type: str = "policy") -> int:
    """Chunk, store, and embed raw text under a source key. Re-ingest replaces. Returns chunk count.

    Embedding is resumable: if it fails partway, re-run `embed_pending` and only the unembedded
    chunks are retried.
    """
    chunks = chunk_text(text)
    if not chunks:
        return 0
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session, session.begin():
        document = await _replace_document(session, source, title, doc_type)
        session.add_all(
            Chunk(document_id=document.id, chunk_idx=i, content=c, token_count=estimate_tokens(c))
            for i, c in enumerate(chunks)
        )
    await embed_pending()
    return len(chunks)


async def _replace_document(session: AsyncSession, source: str, title: str, doc_type: str) -> Document:
    existing = await session.scalar(select(Document).where(Document.source == source))
    if existing:
        await session.delete(existing)  # cascade removes its chunks + embeddings
        await session.flush()
    document = Document(source=source, title=title, doc_type=doc_type)
    session.add(document)
    await session.flush()
    return document


async def embed_pending(batch_size: int = EMBED_BATCH) -> int:
    """Embed chunks that have no embedding for the current model. Safe to re-run."""
    sessionmaker = get_sessionmaker()
    embedded = 0
    while True:
        async with sessionmaker() as session, session.begin():
            chunks = (await session.scalars(_pending_chunks(batch_size))).all()
            if not chunks:
                return embedded
            vectors = await embed_texts([c.content for c in chunks])
            session.add_all(
                Embedding(chunk_id=c.id, embedding=v, model_name=EMBEDDING_MODEL)
                for c, v in zip(chunks, vectors, strict=True)
            )
            embedded += len(chunks)


def _pending_chunks(limit: int):
    already_embedded = select(Embedding.chunk_id).where(Embedding.model_name == EMBEDDING_MODEL)
    return select(Chunk).where(Chunk.id.not_in(already_embedded)).limit(limit)
