"""Re-mask stored messages where masking degraded.

The listener falls back to regex-only when Presidio is unreachable, and NER is what catches names
and places. A message masked on that path keeps them in plain text. It shows up as a redaction
count materially below that of near-identical siblings — see masking_outliers().

This re-runs Presidio over the stored body and redacts what it finds. It does not touch the
listener; it repairs rows that were written while Presidio was down.

Nothing detected is ever printed. The whole point is that these spans are real personal data, and
this repository is public — counts and offsets only.

Dry-run by default. Pass --apply to write.

Usage (from backend/):
    python scripts/remask_outliers.py
    python scripts/remask_outliers.py --apply
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import get_sessionmaker
from scripts.build_study_instrument import (
    load_drafts,
    masking_outliers,
    redaction_count,
)

load_dotenv()

ANALYZER_URL = os.getenv("PRESIDIO_ANALYZER_URL", "http://localhost:5001/analyze")

# What the regex floor cannot catch and therefore what a degraded row is missing. Emails, phones
# and ICs are already covered by the regex layer that runs regardless of Presidio.
_ENTITIES = ["PERSON", "LOCATION", "ORGANIZATION", "NRP"]
_SCORE_THRESHOLD = 0.5
_PLACEHOLDER = "[Redacted]"


async def analyze(client: httpx.AsyncClient, body: str) -> list[dict]:
    response = await client.post(
        ANALYZER_URL,
        json={"text": body, "language": "en", "entities": _ENTITIES,
              "score_threshold": _SCORE_THRESHOLD},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


def redact(body: str, findings: list[dict]) -> str:
    """Replace detected spans back-to-front, so earlier offsets stay valid as we go."""
    spans = sorted(findings, key=lambda f: f["start"], reverse=True)
    out = body
    last_start = len(body) + 1
    for span in spans:
        # Presidio can return overlapping spans; skip any that sits inside one already replaced.
        if span["end"] > last_start:
            continue
        out = out[: span["start"]] + _PLACEHOLDER + out[span["end"]:]
        last_start = span["start"]
    return out


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the repaired bodies")
    args = parser.parse_args()

    drafts = await load_drafts()
    outliers = masking_outliers(drafts)
    if not outliers:
        print("no masking outliers — every message matches its near-duplicates")
        return

    print(f"{len(outliers)} message(s) where masking looks degraded:")
    repairs: list[tuple[str, str, int, int]] = []

    async with httpx.AsyncClient() as client:
        for draft in outliers:
            body = draft["body_masked"] or ""
            findings = await analyze(client, body)
            repaired = redact(body, findings)
            before = redaction_count(draft)
            after = redaction_count({"body_masked": repaired})
            print(f"  {str(draft['id'])[:8]}  {len(findings)} new detection(s), "
                  f"{before} redaction(s) before -> {after} after")
            if findings:
                repairs.append((str(draft["id"]), repaired, before, after))

    if not repairs:
        print("\nPresidio found nothing to add. The gap is not names or places — inspect by hand.")
        return

    if not args.apply:
        print("\ndry run — nothing written. --apply repairs these rows.")
        return

    async with get_sessionmaker()() as session:
        for message_id, repaired, _, _ in repairs:
            await session.execute(
                text("update messages set body_masked = :body where id = :id"),
                {"body": repaired, "id": message_id},
            )
        await session.commit()
    print(f"\nrepaired {len(repairs)} row(s)")
    print("the original remains in the mailbox; this only repairs what we stored")



if __name__ == "__main__":
    asyncio.run(main())
