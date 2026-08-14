"""Ingest a policy PDF into the RAG store.

Usage (from backend/, needs a live DB + GEMINI_API_KEY):

    python scripts/ingest.py /path/to/policy.pdf ["Optional Title"]

Re-ingesting the same path replaces its chunks.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag.ingest import ingest_pdf


async def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python scripts/ingest.py <pdf-path> [title]")
        raise SystemExit(2)
    path = Path(sys.argv[1])
    title = sys.argv[2] if len(sys.argv) > 2 else None
    count = await ingest_pdf(path, title=title)
    print(f"ingested {path.name}: {count} chunks")


if __name__ == "__main__":
    asyncio.run(main())
