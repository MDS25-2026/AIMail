"""S0 primitive proof: embed -> store -> cosine-query it back.

Requires a live Supabase/Postgres (DATABASE_URL) with 0001_rag_tables.sql applied
and a real GEMINI_API_KEY. Run from the backend/ directory:

    python scripts/smoke_primitive.py

It creates a throwaway document, retrieves it, asserts the round-trip, then cleans up.
"""

import asyncio
import sys
from pathlib import Path

import numpy as np
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.constants import EMBEDDING_MODEL
from app.db.models import Chunk, Document, Embedding
from app.db.session import get_sessionmaker
from app.rag.embed import embed_texts
from app.rag.retrieve import retrieve

_SOURCE = "smoke://primitive"
_CONTENT = "The travel reimbursement policy allows claims within 30 days of the trip."


async def main() -> None:
    vectors = await embed_texts([_CONTENT])
    norm = float(np.linalg.norm(vectors[0]))
    assert abs(norm - 1.0) < 1e-3, f"embedding is not L2-normalized (norm={norm})"
    print(f"embed OK  dim={len(vectors[0])} norm={norm:.6f}")

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session, session.begin():
        document = Document(source=_SOURCE, title="smoke", doc_type="policy")
        session.add(document)
        await session.flush()
        chunk = Chunk(document_id=document.id, chunk_idx=0, content=_CONTENT, token_count=12)
        session.add(chunk)
        await session.flush()
        session.add(Embedding(chunk_id=chunk.id, embedding=vectors[0], model_name=EMBEDDING_MODEL))

    hits = await retrieve("How many days do I have to claim reimbursement?", k=1)
    assert hits, "retrieve returned nothing"
    print(f"retrieve OK  score={hits[0]['similarity_score']:.4f}  title={hits[0]['source_title']}")
    assert hits[0]["similarity_score"] > 0.3, "semantically-related query scored too low"

    async with sessionmaker() as session, session.begin():
        stored = await session.scalar(select(Document).where(Document.source == _SOURCE))
        if stored:
            await session.delete(stored)
    print("cleanup OK")


if __name__ == "__main__":
    asyncio.run(main())
