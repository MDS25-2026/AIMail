import asyncio
import hashlib

from sqlalchemy import text

from app.db.session import get_sessionmaker


async def main():
    print("Verifying cryptographic hash chain in audit_log...")
    async with get_sessionmaker()() as session:
        result = await session.execute(
            text(
                "SELECT id, action, detail, success, extract(epoch from created_at), prev_hash, current_hash FROM audit_log ORDER BY created_at ASC, id ASC"
            )
        )
        rows = result.fetchall()

    if not rows:
        print("Audit log is empty.")
        return

    last_hash = "0000000000000000000000000000000000000000000000000000000000000000"
    errors = 0

    for row in rows:
        id_, action, detail, success, ts_epoch, prev_hash, current_hash = row
        if prev_hash != last_hash:
            print(
                f"[X] BROKEN CHAIN at ID {id_}: expected prev_hash {last_hash}, got {prev_hash}"
            )
            errors += 1

        detail_str = detail if detail is not None else ""
        success_str = str(success).lower() if success is not None else "false"
        ts_str = str(ts_epoch)

        # Digest: last_hash + action + detail + success + timestamp
        raw = f"{last_hash}{action}{detail_str}{success_str}{ts_str}"
        computed_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()

        if computed_hash != current_hash:
            print(
                f"[!] TAMPERING DETECTED at ID {id_}: computed hash {computed_hash}, db hash {current_hash}"
            )
            errors += 1

        last_hash = current_hash

    if errors == 0:
        print(
            f"[OK] Audit log is perfectly intact! Verified {len(rows)} chained records."
        )
    else:
        print(f"[!] Verification failed with {errors} errors.")


if __name__ == "__main__":
    asyncio.run(main())
