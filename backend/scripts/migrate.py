"""Bring the database's schema up to date (app/db/migrate.py).

Usage (from backend/):
    python scripts/migrate.py               apply every pending migration
    python scripts/migrate.py --status      list pending migrations
    python scripts/migrate.py --baseline V  record migrations up to V as applied, without running them
                                            (once, for a database migrated by hand before the ledger)
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.migrate import apply_pending, baseline, pending


async def main(args: argparse.Namespace) -> None:
    if args.baseline:
        print("recorded as applied:", ", ".join(await baseline(args.baseline)) or "nothing new")
        return
    if args.status:
        print("pending:", ", ".join(await pending()) or "none")
        return
    print("applied:", ", ".join(await apply_pending()) or "nothing pending")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--baseline", metavar="VERSION")
    asyncio.run(main(parser.parse_args()))
