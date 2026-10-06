"""Regenerate stored drafts so they carry per-gate critic results.

Every draft generated before the gate redesign (#68) has `critic_checks` NULL — the four checks
existed in the prompt but nothing read them, so nothing was stored. Those rows cannot answer
"which gate flagged this", only "what scalar did the model report", which is the number the
redesign exists to stop relying on.

Dry-run by default, matching backfill_critic_confidence.py. Pass --apply to write.

Each message is regenerated independently: one failure is reported and skipped rather than
aborting the batch, because a rate limit partway through should not cost the rows already done.

Usage (from backend/):
    python scripts/regenerate_drafts.py                    # show what would be regenerated
    python scripts/regenerate_drafts.py --apply            # regenerate, 15s apart
    python scripts/regenerate_drafts.py --apply --delay 8  # faster, if quota allows
"""

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.dashboard import regenerate_email
from app.db.session import get_sessionmaker

# ~6 Gemini calls per email on the free tier, so pace by default rather than discovering the
# rate limit halfway through a batch.
_DEFAULT_DELAY_SECONDS = 15.0

_TARGETS = text("""
    select id, critic_confidence, critic_checks is not null as has_checks
    from messages
    where coalesce(draft_reply, '') <> ''
    order by critic_confidence nulls first
""")


async def load_targets(only_missing: bool) -> list[tuple[str, float | None, bool]]:
    async with get_sessionmaker()() as session:
        rows = (await session.execute(_TARGETS)).all()
    selected = [(str(r[0]), r[1], r[2]) for r in rows]
    return [row for row in selected if not row[2]] if only_missing else selected


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="regenerate (default: dry run)")
    parser.add_argument("--delay", type=float, default=_DEFAULT_DELAY_SECONDS,
                        help="seconds between messages, to stay inside the rate limit")
    parser.add_argument("--all", action="store_true",
                        help="include drafts that already carry critic_checks")
    args = parser.parse_args()

    targets = await load_targets(only_missing=not args.all)
    if not targets:
        print("nothing to regenerate — every stored draft already carries per-gate results")
        return

    print(f"{len(targets)} draft(s) to regenerate")
    for message_id, confidence, _ in targets:
        print(f"  {message_id}  confidence={confidence}")

    if not args.apply:
        print(f"\ndry run — nothing written. --apply regenerates, ~{args.delay:.0f}s apart.")
        return

    succeeded, failed = 0, []
    for index, (message_id, _, _) in enumerate(targets, 1):
        try:
            email = await regenerate_email(message_id)
        except Exception as exc:  # noqa: BLE001 - one bad row must not end the batch
            failed.append((message_id, repr(exc)))
            print(f"  [{index}/{len(targets)}] {message_id} FAILED: {exc!r}")
        else:
            if email is None:
                failed.append((message_id, "message not found"))
                print(f"  [{index}/{len(targets)}] {message_id} not found")
            else:
                succeeded += 1
                print(f"  [{index}/{len(targets)}] {message_id} ok")
        if index < len(targets):
            await asyncio.sleep(args.delay)

    print(f"\nregenerated {succeeded}, failed {len(failed)}")
    for message_id, reason in failed:
        print(f"  {message_id}: {reason}")


if __name__ == "__main__":
    asyncio.run(main())
