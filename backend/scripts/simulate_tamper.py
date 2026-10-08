"""Script to simulate database tampering on audit_log for testing (#148 / PDPA).

Usage:
    python scripts/simulate_tamper.py tamper   # Modifies a log record to trigger cryptographic breach
    python scripts/simulate_tamper.py restore  # Restores the original authentic record
    python scripts/simulate_tamper.py status   # Checks current ledger integrity
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.audit_routes import _SUMMARY
from app.db.session import get_sessionmaker

BACKUP_FILE = Path(__file__).parent / ".tamper_backup.json"


async def check_status():
    async with get_sessionmaker()() as session:
        summary = (await session.execute(_SUMMARY)).one()
    state = "[OK] chain intact" if summary.is_intact else "[!] TAMPERING DETECTED: the chain is broken"
    print(f"{state} ({summary.chained} chained records)")


async def _edit_past_the_guard(session, target_id: str, detail: str) -> None:
    """What an attacker with full database rights would do: switch off the append-only guard (0025)
    for one transaction and edit a row. The chain check must still catch it."""
    await session.execute(text("ALTER TABLE audit_log DISABLE TRIGGER trg_audit_append_only"))
    await session.execute(text("UPDATE audit_log SET detail = :d WHERE id = :id"), {"d": detail, "id": target_id})
    await session.execute(text("ALTER TABLE audit_log ENABLE TRIGGER trg_audit_append_only"))
    await session.commit()


async def tamper_record():
    async with get_sessionmaker()() as session:
        sql_find = "SELECT id, detail FROM audit_log WHERE chain_seq IS NOT NULL ORDER BY chain_seq DESC LIMIT 1"
        res = await session.execute(text(sql_find))
        row = res.fetchone()
        if not row:
            print("[!] No audit log record found to tamper.")
            return

        target_id = str(row[0])
        original_detail = row[1] or ""

        # Save backup for clean restoration
        BACKUP_FILE.write_text(
            json.dumps({"id": target_id, "original_detail": original_detail})
        )

        tampered_detail = '{"tampered":true}'
        await _edit_past_the_guard(session, target_id, tampered_detail)

    print(f"[TAMPERED] Modified record ID: {target_id}")
    print(f"Original detail: {original_detail}")
    print(f"Tampered detail: {tampered_detail}")
    print("\nOpen or refresh http://localhost:8090/audit to see the live breach alert!")


async def restore_record():
    if not BACKUP_FILE.exists():
        print("[!] No backup file found. Cannot restore automatically.")
        return

    data = json.loads(BACKUP_FILE.read_text())
    target_id = data["id"]
    original_detail = data["original_detail"]

    async with get_sessionmaker()() as session:
        await _edit_past_the_guard(session, target_id, original_detail)

    BACKUP_FILE.unlink(missing_ok=True)
    print(f"[RESTORED] Record ID: {target_id} restored to authentic state.")
    print(f"Detail restored: {original_detail}")
    print(
        "\nOpen or refresh http://localhost:8090/audit to see [VERIFIED] Intact ledger restored."
    )


def main():
    parser = argparse.ArgumentParser(description="Simulate audit log tampering")
    parser.add_argument(
        "action", choices=["tamper", "restore", "status"], help="Action to execute"
    )
    args = parser.parse_args()

    if args.action == "tamper":
        asyncio.run(tamper_record())
    elif args.action == "restore":
        asyncio.run(restore_record())
    elif args.action == "status":
        asyncio.run(check_status())


if __name__ == "__main__":
    main()
