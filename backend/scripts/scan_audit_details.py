"""Count audit rows whose detail text looks like it holds a personal detail (specs/features/privacy-gaps.md).

Read-only. Uses the typed-text patterns (email, phone, IC, passport, card). Prints counts and row ids
only, never the matched text. Rows before the structured format (2026-10-08) were free text, so they
are counted separately. Expect false positives: ids and hashes can look like phone or IC numbers.

Usage (from backend/): python scripts/scan_audit_details.py [--ids N]
"""

import argparse
import asyncio
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.typed_text import mask_typed_text
from app.db.models import AuditLog
from app.db.session import get_engine, get_sessionmaker

STRUCTURED_SINCE = datetime(2026, 10, 8, tzinfo=timezone.utc)
KINDS = ("EMAIL", "PHONE", "IC", "PASSPORT", "CARD")


def _kinds_in(detail: str) -> list[str]:
    masked = mask_typed_text(detail)
    return [kind for kind in KINDS if f"[{kind}_REDACTED]" in masked and f"[{kind}_REDACTED]" not in detail]


async def scan() -> dict[tuple[str, str], list[str]]:
    """(era, kind) -> ids of the rows that matched."""
    found: dict[tuple[str, str], list[str]] = defaultdict(list)
    async with get_sessionmaker()() as session:
        rows = await session.execute(select(AuditLog.id, AuditLog.detail, AuditLog.created_at)
                                     .where(AuditLog.detail.is_not(None)))
        for row_id, detail, created_at in rows:
            era = "structured" if created_at >= STRUCTURED_SINCE else "free text"
            for kind in _kinds_in(detail):
                found[(era, kind)].append(str(row_id))
    return found


async def main(show_ids: int) -> None:
    try:
        found = await scan()
    finally:
        await get_engine().dispose()
    if not found:
        print("no audit row looks like it holds an email address, phone, IC, passport or card number")
        return
    for (era, kind), ids in sorted(found.items()):
        print(f"{era:<10} {kind:<8} {len(ids):>5} row(s)  e.g. {', '.join(ids[:show_ids])}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ids", type=int, default=3, help="row ids to print per kind")
    asyncio.run(main(parser.parse_args().ids))
