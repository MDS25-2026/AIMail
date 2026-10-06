"""Null out critic_confidence on messages that were never scored.

The NA path returns confidence None, and `float(... or 0.0)` stored that as 0.0, so
"no draft was generated" became indistinguishable from "the critic rejected this" in
every statistic over the column. The write path is fixed; this repairs existing rows.

Only rows with an empty draft_reply are touched. A genuine 0.0 on a real draft is a
real score and is left alone.

Usage (from backend/):
    python scripts/backfill_critic_confidence.py            # dry run, prints the count
    python scripts/backfill_critic_confidence.py --apply    # writes
"""

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import get_engine

_TARGET = "critic_confidence = 0 AND coalesce(draft_reply, '') = ''"


async def run(apply: bool) -> None:
    async with get_engine().begin() as conn:
        affected = (await conn.execute(
            text(f"SELECT count(*) FROM messages WHERE {_TARGET}")
        )).scalar_one()
        if not apply:
            print(f"dry run: {affected} rows would be set to NULL; re-run with --apply")
            return
        await conn.execute(text(f"UPDATE messages SET critic_confidence = NULL WHERE {_TARGET}"))
        print(f"set {affected} rows to NULL")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write; omit for a dry run")
    asyncio.run(run(parser.parse_args().apply))


if __name__ == "__main__":
    main()
