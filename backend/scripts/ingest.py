"""Ingest a policy PDF into one account's document library.

Usage (from backend/, needs a live DB + GOOGLE_API_KEY):

    python scripts/ingest.py /path/to/policy.pdf --owner you@example.com [--title "Optional Title"]

Re-ingesting the same path for the same owner replaces its chunks.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.ownership import scope_of_email
from app.rag.ingest import ingest_pdf


async def main(args: argparse.Namespace) -> None:
    try:
        scope = await scope_of_email(args.owner)
    except LookupError as exc:
        raise SystemExit(str(exc)) from exc
    count = await ingest_pdf(args.pdf, scope=scope, title=args.title or None)
    print(f"ingested {args.pdf.name} for {args.owner}: {count} chunks")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--owner", required=True, help="sign-in email of the account the document belongs to")
    parser.add_argument("--title", default="")
    asyncio.run(main(parser.parse_args()))
