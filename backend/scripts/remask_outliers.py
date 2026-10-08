"""Re-mask stored messages where masking degraded.

The listener falls back to regex-only when Presidio is unreachable, and NER is what catches names
and places. A message masked on that path keeps them in plain text. It shows up as a redaction
count materially below that of near-identical siblings — see masking_outliers().

This re-runs Presidio over the stored body, subject, snippet and AI summary, and redacts what it
finds. An unsent row also loses its cached draft, so the poller drafts again from the repaired
text; a sent row keeps its draft, the record of what went out. It does not touch the listener; it
repairs rows that were written while Presidio was down.

Nothing detected is ever printed. The whole point is that these spans are real personal data, and
this repository is public — counts and offsets only.

Dry-run by default. Pass --apply to write.

--all checks every masked message instead of only the outliers: the outlier heuristic needs a
near-identical sibling to compare against, so a degraded one-off is invisible to it.

Usage (from backend/):
    python scripts/remask_outliers.py
    python scripts/remask_outliers.py --all
    python scripts/remask_outliers.py --apply
"""

import argparse
import asyncio
import sys
from collections import Counter
from pathlib import Path

import httpx
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.db.session import get_sessionmaker
from scripts.build_study_instrument import (
    load_drafts,
    masking_outliers,
    redaction_count,
)

# What the regex floor cannot catch and therefore what a degraded row is missing. Emails, phones
# and ICs are already covered by the regex layer that runs regardless of Presidio.
_ENTITIES = ["PERSON", "LOCATION", "ORGANIZATION", "NRP"]
_SCORE_THRESHOLD = 0.5
_PLACEHOLDER = "[Redacted]"

# Text columns derived from the same email, which carry the same names as the body.
_DERIVED_TEXT = ("subject", "snippet_masked", "ai_summary")
# Cleared on an unsent row so the poller regenerates from the repaired body.
_REGENERATE = {
    "draft_reply": None, "rag_sources": None, "action_items": None, "critic_confidence": None,
    "critic_attempts": None, "critic_checks": None, "needs_human_review": None,
    "generated_at": None, "generation_attempts": 0,
}
_ALL_MASKED = text("""
    select id, body_masked from messages
    where masking_status = 'complete' and coalesce(body_masked, '') <> ''
""")
_ROW = text("select subject, snippet_masked, ai_summary, sent_at from messages where id = :id")


def repair_update(row: dict, remasked: dict[str, str]) -> dict:
    """Column values for one repaired row. A sent row keeps its draft: it records what went out."""
    return dict(remasked) if row.get("sent_at") else {**remasked, **_REGENERATE}


async def analyze(client: httpx.AsyncClient, body: str) -> list[dict]:
    response = await client.post(
        get_settings().presidio_analyzer_url,
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
    parser.add_argument("--all", action="store_true", help="check every masked message")
    args = parser.parse_args()

    if args.all:
        async with get_sessionmaker()() as session:
            outliers = [dict(r) for r in (await session.execute(_ALL_MASKED)).mappings().all()]
    else:
        outliers = masking_outliers(await load_drafts())
    if not outliers:
        print("no masking outliers — every message matches its near-duplicates")
        return

    scope = "masked message(s) checked" if args.all else "message(s) where masking looks degraded"
    print(f"{len(outliers)} {scope}:")
    repairs: list[tuple[str, dict]] = []

    async with httpx.AsyncClient() as client, get_sessionmaker()() as session:
        for draft in outliers:
            row = dict((await session.execute(_ROW, {"id": draft["id"]})).mappings().one())
            fields = {"body_masked": draft["body_masked"] or ""}
            fields |= {name: row[name] for name in _DERIVED_TEXT if row[name]}
            remasked, kinds = {}, Counter()
            for name, value in fields.items():
                findings = await analyze(client, value)
                kinds.update(f["entity_type"] for f in findings)
                remasked[name] = redact(value, findings)
            detections = sum(kinds.values())
            before = redaction_count(draft)
            after = redaction_count({"body_masked": remasked["body_masked"]})
            print(f"  {str(draft['id'])[:8]}  {detections} new detection(s) across {len(fields)} "
                  f"field(s); body {before} redaction(s) before -> {after} after"
                  f"{'' if row['sent_at'] else ', draft will regenerate'}"
                  f"{'  ' + dict(kinds).__repr__() if kinds else ''}")
            if detections:
                repairs.append((str(draft["id"]), repair_update(row, remasked)))

    if not repairs:
        print("\nPresidio found nothing to add. The gap is not names or places — inspect by hand.")
        return

    if not args.apply:
        print("\ndry run — nothing written. --apply repairs these rows.")
        return

    async with get_sessionmaker()() as session:
        for message_id, update in repairs:
            # Column names come from this file's fixed lists, never from data.
            assignments = ", ".join(f"{column} = :{column}" for column in update)
            await session.execute(text(f"update messages set {assignments} where id = :id"),
                                  {**update, "id": message_id})
        await session.commit()
    print(f"\nrepaired {len(repairs)} row(s)")
    print("the original remains in the mailbox; this only repairs what we stored")


if __name__ == "__main__":
    asyncio.run(main())
