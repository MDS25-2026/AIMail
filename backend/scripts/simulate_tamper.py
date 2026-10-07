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

from app.db.session import get_sessionmaker
from sqlalchemy import text

BACKUP_FILE = Path(__file__).parent / ".tamper_backup.json"


async def check_status():
    sql = """
    SELECT 
        id,
        action,
        detail,
        current_hash = encode(digest(
            COALESCE(prev_hash, '0000000000000000000000000000000000000000000000000000000000000000') || 
            COALESCE(action, '') || 
            COALESCE(detail, '') || 
            COALESCE(success::text, 'false') || 
            COALESCE(user_id::text, '') || 
            extract(epoch from created_at)::text,
            'sha256'
        ), 'hex') AS is_valid
    FROM audit_log
    WHERE current_hash IS NOT NULL
    ORDER BY created_at DESC, id DESC
    LIMIT 10
    """
    async with get_sessionmaker()() as session:
        res = await session.execute(text(sql))
        rows = res.fetchall()

    if not rows:
        print("[!] No hashed audit rows found.")
        return

    invalid_rows = [r for r in rows if r[3] is False]
    if invalid_rows:
        print(f"[!] TAMPERING DETECTED! Found {len(invalid_rows)} compromised records:")
        for r in invalid_rows:
            print(f"    - ID: {r[0]} | Action: {r[1]} | Detail: {r[2][:60]}")
    else:
        print(
            f"[OK] Ledger is perfectly intact. Verified {len(rows)} recent records without tampering."
        )


async def tamper_record():
    async with get_sessionmaker()() as session:
        # Pick the most recent hashed row
        sql_find = "SELECT id, detail FROM audit_log WHERE current_hash IS NOT NULL ORDER BY created_at DESC, id DESC LIMIT 1"
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

        tampered_detail = "UNAUTHORIZED TAMPERED TEXT: Rogue admin altered audit record"
        sql_tamper = "UPDATE audit_log SET detail = :tampered WHERE id = :id"
        await session.execute(
            text(sql_tamper), {"tampered": tampered_detail, "id": target_id}
        )
        await session.commit()

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
        sql_restore = "UPDATE audit_log SET detail = :orig WHERE id = :id"
        await session.execute(
            text(sql_restore), {"orig": original_detail, "id": target_id}
        )
        await session.commit()

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
