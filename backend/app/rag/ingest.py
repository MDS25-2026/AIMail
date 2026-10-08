"""Ingest a policy PDF: extract, chunk, store, embed. Idempotent per source."""

import logging
from pathlib import Path

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import EMBEDDING_TAG
from app.core.ownership import Scope
from app.core.providers import Provider
from app.db.models import (
    Chunk,
    DocType,
    Document,
    Embedding,
    LocalEmbedding,
    UserPreferences,
)
from app.db.session import get_sessionmaker
from app.rag.chunk import (
    SECTION_KEY,
    Piece,
    chunk_sections,
    estimate_tokens,
    extract_pdf_text,
)
from app.rag.embed import EmbeddingError, embed_documents
from app.rag.local_embed import embed_documents_locally, local_model, local_tag
from app.rag.mask import mask_document

logger = logging.getLogger(__name__)

EMBED_BATCH = 100


async def ingest_pdf(
    path: Path, *, scope: Scope, title: str | None = None, doc_type: DocType = DocType.POLICY
) -> int:
    """Ingest one PDF. Re-ingesting the same path replaces its chunks. Returns chunk count."""
    return await ingest_text(str(path), title or path.stem, extract_pdf_text(path),
                             scope=scope, doc_type=doc_type)


async def ingest_text(
    source: str, title: str, text: str, *, scope: Scope, doc_type: DocType = DocType.POLICY
) -> int:
    """Chunk, store, and embed raw text under a source key. Re-ingest replaces. Returns chunk count.

    Embedding is resumable: if it fails partway, re-run `embed_pending` and only the unembedded
    chunks are retried.
    """
    # Nothing to store: answered before masking, which needs Presidio and the settings.
    if not text.strip():
        return 0
    pieces = chunk_sections(await mask_document(text))
    if not pieces:
        return 0
    await store_chunks(source, title, pieces, scope=scope, doc_type=doc_type)
    await embed_pending()
    await embed_pending_locally_logged()
    return len(pieces)


async def store_chunks(
    source: str, title: str, pieces: list[Piece], *, scope: Scope, doc_type: DocType
) -> None:
    """Already-masked chunks under a source key, replacing that owner's earlier copy. Not embedded."""
    async with get_sessionmaker()() as session, session.begin():
        document = await _replace_document(session, scope, source, title, doc_type)
        session.add_all(
            Chunk(document_id=document.id, chunk_idx=i, content=piece.content,
                  token_count=estimate_tokens(piece.content),
                  meta={SECTION_KEY: piece.section} if piece.section else None)
            for i, piece in enumerate(pieces)
        )


async def _replace_document(
    session: AsyncSession, scope: Scope, source: str, title: str, doc_type: DocType
) -> Document:
    # Re-uploading replaces only this owner's copy; another user's same-named file is untouched.
    existing = await session.scalar(
        select(Document).where(Document.source == source, scope.where(Document.user_id))
    )
    if existing:
        await session.delete(existing)  # cascade removes its chunks + embeddings
        await session.flush()
    document = Document(source=source, title=title, doc_type=doc_type, user_id=scope.owner_id)
    session.add(document)
    await session.flush()
    return document


async def embed_pending(batch_size: int = EMBED_BATCH) -> int:
    """Embed chunks that have no Gemini embedding for the current model. Safe to re-run.

    A Private-mode user's chunks are skipped: Gemini embedding would send them to Google.
    """
    sessionmaker = get_sessionmaker()
    embedded = 0
    while True:
        async with sessionmaker() as session, session.begin():
            chunks = (await session.scalars(_pending_for_gemini(batch_size))).all()
            if not chunks:
                return embedded
            vectors = await embed_documents([c.content for c in chunks])
            session.add_all(
                Embedding(chunk_id=c.id, embedding=v, model_name=EMBEDDING_TAG)
                for c, v in zip(chunks, vectors, strict=True)
            )
            embedded += len(chunks)


async def embed_pending_locally(batch_size: int = EMBED_BATCH) -> int:
    """Embed every chunk with no local vector, so switching Private mode on finds documents at once."""
    if not local_model():
        return 0
    sessionmaker = get_sessionmaker()
    embedded = 0
    while True:
        async with sessionmaker() as session, session.begin():
            chunks = (await session.scalars(_pending_for_local(batch_size))).all()
            if not chunks:
                return embedded
            vectors = await embed_documents_locally([c.content for c in chunks])
            session.add_all(
                LocalEmbedding(chunk_id=c.id, embedding=v, model_name=local_tag())
                for c, v in zip(chunks, vectors, strict=True)
            )
            embedded += len(chunks)


async def embed_pending_locally_logged() -> None:
    """At upload the Gemini side is what the user waits for; a local failure is retried by the poll."""
    try:
        await embed_pending_locally()
    except EmbeddingError:
        logger.exception("local embedding failed; the background pass will retry")


def _pending(already_embedded: Select, limit: int) -> Select:
    # SKIP LOCKED: the upload, the send and the background pass may run at once; each takes its own rows.
    return (select(Chunk).where(Chunk.id.not_in(already_embedded))
            .limit(limit).with_for_update(skip_locked=True, of=Chunk))


def _pending_for_gemini(limit: int) -> Select:
    already_embedded = select(Embedding.chunk_id).where(Embedding.model_name == EMBEDDING_TAG)
    private_users = select(UserPreferences.user_id).where(
        UserPreferences.draft_provider == Provider.LOCAL)
    private_documents = select(Document.id).where(Document.user_id.in_(private_users))
    return _pending(already_embedded, limit).where(Chunk.document_id.not_in(private_documents))


def _pending_for_local(limit: int) -> Select:
    already_embedded = select(LocalEmbedding.chunk_id).where(LocalEmbedding.model_name == local_tag())
    return _pending(already_embedded, limit)
