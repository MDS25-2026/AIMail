"""Pull study responses out of Supabase into the CSV analyse_study.py reads.

Needs the service key, not the anon key: the table's policy lets anonymous visitors insert and
nothing else, so the key in the public page cannot read responses back. That is the point of it.

Participant numbers are assigned here, in submission order. They are sequential and carry no
information about who submitted — the page collects nothing that could identify anyone, and this
must not reintroduce it.

Usage (from backend/):
    python scripts/fetch_study_responses.py                       # writes study_responses.csv
    python scripts/fetch_study_responses.py --out responses.csv
"""

import argparse
import csv
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

load_dotenv()

TABLE = "study_responses"

# Written in the order the analysis expects, so the CSV needs no reshaping afterwards.
_PART1_ITEMS = 9
_EXPLAIN = (4, 7, 8)
_GATES = ("g1", "g2", "g3", "g4")


def header(n_drafts: int) -> list[str]:
    columns = ["participant", "submitted_at", "consent", "role"]
    columns += [f"item_{i}" for i in range(1, _PART1_ITEMS + 1)]
    columns += [f"other_{i}" for i in range(1, _PART1_ITEMS + 1) if i not in _EXPLAIN]
    columns += [f"explain_{i}" for i in _EXPLAIN]
    columns += ["q1_not_fitting", "q2_sender_list"]
    for index in range(1, n_drafts + 1):
        columns += [f"{gate}_{index}" for gate in _GATES]
        columns += [f"send_{index}", f"comment_{index}"]
    return columns


def count_drafts(rows: list[dict]) -> int:
    """Infer the Part-2 length from the data rather than hardcoding it here and in the generator."""
    highest = 0
    for row in rows:
        for key in row.get("answers", {}):
            if key.startswith("send_"):
                highest = max(highest, int(key.split("_")[1]))
    return highest


def fetch(url: str, key: str) -> list[dict]:
    response = httpx.get(
        f"{url.rstrip('/')}/rest/v1/{TABLE}",
        params={"select": "created_at,answers", "order": "created_at.asc"},
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="study_responses.csv")
    args = parser.parse_args()

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")

    rows = fetch(url, key)
    if not rows:
        print(f"no responses in {TABLE} yet")
        return

    n_drafts = count_drafts(rows)
    columns = header(n_drafts)

    with Path(args.out).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for number, row in enumerate(rows, 1):
            answers = dict(row.get("answers") or {})
            answers["participant"] = number
            answers.setdefault("submitted_at", row.get("created_at", ""))
            writer.writerow(answers)

    unexpected = {
        key for row in rows for key in (row.get("answers") or {})
    } - set(columns)
    print(f"  wrote {args.out}: {len(rows)} response(s), {n_drafts} draft(s) in Part 2")
    if unexpected:
        # A generator change that the analysis has not caught up with shows up here rather than as
        # a silently dropped column.
        print(f"  NOTE: answers contained keys the CSV does not carry: {sorted(unexpected)}")


if __name__ == "__main__":
    main()
