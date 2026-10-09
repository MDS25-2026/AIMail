"""Knowledge-base inventory: what documents are stored and how many chunks each has, and removing one."""

from typing import TypedDict
from uuid import UUID

from sqlalchemy import delete, func, select

from app.core.ownership import Scope
from app.db.models import Chunk, DocType, Document
from app.db.session import get_sessionmaker


class DocumentSummary(TypedDict):
    document_id: UUID
    title: str
    source: str
    doc_type: str
    chunk_count: int


async def list_documents(scope: Scope) -> list[DocumentSummary]:
    stmt = (
        select(
            Document.id,
            Document.title,
            Document.source,
            Document.doc_type,
            func.count(Chunk.id),
        )
        .outerjoin(Chunk, Chunk.document_id == Document.id)
        # Past replies are search items the user manages on the writing-style card, not documents.
        .where(scope.where(Document.user_id), Document.doc_type.is_distinct_from(DocType.SENT_REPLY))
        .group_by(Document.id)
        .order_by(Document.title)
    )
    async with get_sessionmaker()() as session:
        rows = (await session.execute(stmt)).all()
    return [
        DocumentSummary(
            document_id=row[0],
            title=row[1] or "",
            source=row[2],
            doc_type=row[3] or "",
            chunk_count=row[4],
        )
        for row in rows
    ]


async def delete_document(document_id: UUID, scope: Scope) -> bool:
    """False when it is not in this scope's library: someone else's file looks like a missing one.

    Past replies are not in the library, so they cannot be removed here; the writing-style card does.
    """
    async with get_sessionmaker()() as session, session.begin():
        deleted = await session.scalar(
            delete(Document)
            .where(Document.id == document_id, scope.where(Document.user_id),
                   Document.doc_type.is_distinct_from(DocType.SENT_REPLY))
            .returning(Document.id)
        )
    return deleted is not None


class ChunkDetail(TypedDict):
    id: UUID
    chunk_idx: int
    section: str | None
    content: str


class DocumentDetail(TypedDict):
    document_id: UUID
    title: str
    source: str
    doc_type: str
    chunk_count: int
    content: str
    chunks: list[ChunkDetail]


async def get_document_detail(document_id: UUID, scope: Scope) -> DocumentDetail | None:
    """Fetch a document by ID with all its chunks ordered by chunk_idx, reassembling the full text."""
    async with get_sessionmaker()() as session:
        doc = await session.scalar(
            select(Document).where(
                Document.id == document_id,
                scope.where(Document.user_id),
                Document.doc_type.is_distinct_from(DocType.SENT_REPLY),
            )
        )
        if not doc:
            return None

        chunks = (
            await session.scalars(
                select(Chunk)
                .where(Chunk.document_id == document_id)
                .order_by(Chunk.chunk_idx.asc())
            )
        ).all()

        chunk_details: list[ChunkDetail] = [
            ChunkDetail(
                id=c.id,
                chunk_idx=c.chunk_idx,
                section=(c.meta or {}).get("section") if c.meta else None,
                content=c.content,
            )
            for c in chunks
        ]
        full_text = "\n\n".join(c.content for c in chunks)

        return DocumentDetail(
            document_id=doc.id,
            title=doc.title or "",
            source=doc.source,
            doc_type=doc.doc_type or "",
            chunk_count=len(chunks),
            content=full_text,
            chunks=chunk_details,
        )
