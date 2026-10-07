"""Check the whole audit hash chain (specs/features/sender-verification-and-audit.md).

Usage (from backend/): python scripts/verify_audit_chain.py

Uses the same check as GET /audit: each row's hash, its link to the row before, and no gap in
chain_seq. Prints the head hash; recorded outside the database, it shows a rebuilt chain.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.audit_routes import _CHAIN, _SUMMARY
from app.db.session import get_sessionmaker

_BROKEN = text(_CHAIN + """
SELECT a.chain_seq, a.id, a.action FROM audit_log a JOIN chain c ON c.id = a.id
WHERE NOT c.is_valid ORDER BY a.chain_seq
""")


async def main() -> int:
    async with get_sessionmaker()() as session:
        summary = (await session.execute(_SUMMARY)).one()
        broken = (await session.execute(_BROKEN)).all()
    for row in broken:
        print(f"[BROKEN] seq {row.chain_seq} id {row.id} action {row.action}")
    print(f"{summary.chained} chained records; head hash {summary.head}")
    print("[OK] chain intact" if summary.is_intact else f"[FAILED] {len(broken)} records break the chain")
    return 0 if summary.is_intact else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
