"""Seed the DB with sample policy chunks so the retrieval demo has content.

Usage (from backend/, needs a live DB + GEMINI_API_KEY):

    python scripts/seed_demo.py

Idempotent: replaces the demo document on re-run. Sample text only, no real PII.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.constants import EMBEDDING_MODEL
from app.db.models import Chunk, Document, Embedding
from app.db.session import get_sessionmaker
from app.rag.chunk import estimate_tokens
from app.rag.embed import embed_texts

_SOURCE = "demo://employee-handbook"
_SNIPPETS = [
    (
        "Employees may work remotely up to three days per week with manager approval. "
        "Fully remote arrangements require director sign-off."
    ),
    (
        "Travel reimbursement claims must be submitted within 30 days of the trip, with itemised "
        "receipts attached. Claims made after 30 days require finance approval."
    ),
    (
        "Annual leave accrues at 1.75 days per month. Unused leave up to 10 days may be carried "
        "over into the next calendar year; anything beyond that is forfeited."
    ),
    (
        "Company data classified as confidential must not be shared with external parties or "
        "third-party AI tools without prior written authorisation from the data owner."
    ),
    (
        "Any expense claim over 500 dollars requires pre-approval from a department head before "
        "the purchase is made. Unapproved purchases may not be reimbursed."
    ),
    (
        "Sick leave requires notifying your manager before 10am on the day of absence. A medical "
        "certificate is required for any absence longer than two consecutive days."
    ),
]


async def main() -> None:
    vectors = await embed_texts(_SNIPPETS)
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session, session.begin():
        existing = await session.scalar(select(Document).where(Document.source == _SOURCE))
        if existing:
            await session.delete(existing)
            await session.flush()
        document = Document(source=_SOURCE, title="Employee Handbook (demo)", doc_type="policy")
        session.add(document)
        await session.flush()
        for idx, (text, vector) in enumerate(zip(_SNIPPETS, vectors, strict=True)):
            chunk = Chunk(
                document_id=document.id, chunk_idx=idx, content=text, token_count=estimate_tokens(text)
            )
            session.add(chunk)
            await session.flush()
            session.add(Embedding(chunk_id=chunk.id, embedding=vector, model_name=EMBEDDING_MODEL))
    print(f"seeded {len(_SNIPPETS)} policy chunks under {_SOURCE}")


if __name__ == "__main__":
    asyncio.run(main())
