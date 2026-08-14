"""Knowledge-base inventory: what documents are stored and how many chunks each has."""

from typing import TypedDict
from uuid import UUID

from sqlalchemy import func, select

from app.db.models import Chunk, Document
from app.db.session import get_sessionmaker


class DocumentSummary(TypedDict):
    document_id: UUID
    title: str
    source: str
    doc_type: str
    chunk_count: int


async def list_documents() -> list[DocumentSummary]:
    stmt = (
        select(
            Document.id,
            Document.title,
            Document.source,
            Document.doc_type,
            func.count(Chunk.id),
        )
        .outerjoin(Chunk, Chunk.document_id == Document.id)
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
