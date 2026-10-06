"""Characterise the critic's confidence over real emails, without touching the database.

Posts holdout emails straight at Lane C's `/process-email` and records what comes back, so the
critic can be measured at any N without seeding rows into the shared demo inbox.

Each email costs roughly six Gemini calls, and every draft that fails the 0.8 gate costs six more
(the refine loop retries three times). On the free tier that is a few dozen emails per day, so the
run is **resumable**: rows already in the output are skipped, and a rate-limit stop costs only the
row it hit. Re-run the same command to continue.

Usage (from backend/, with the agent running on :8001):
    python scripts/eval_critic.py holdout_to_label.csv --limit 20 --out critic_eval.csv
    python scripts/eval_critic.py holdout_to_label.csv --summary-only --out critic_eval.csv
"""

import argparse
import asyncio
import csv
import sys
from collections import Counter
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.rag.retrieve import retrieve
from app.rag.utils import format_rag_context

FIELDS = [
    "row", "gold_label", "category", "confidence",
    "needs_human_review", "attempts", "n_issues", "issues", "action_items", "error",
]

# A single /process-email can chain six Gemini calls plus three refine rounds; the agent's own
# per-call timeout is 30s, so anything shorter here fails on slow-but-healthy runs.
REQUEST_TIMEOUT_SECONDS = 240.0
CONSECUTIVE_FAILURE_LIMIT = 3


def load_done(out_path: Path) -> set[int]:
    """Rows that *succeeded*, so a resumed run skips those but retries the failures."""
    if not out_path.exists():
        return set()
    with out_path.open(newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(handle)
        return {int(r["row"]) for r in rows if r.get("row") and not r.get("error")}

def columns_match(out_path: Path) -> bool:
    """A file written under a different FIELDS layout is silently misparsed, not rejected."""
    if not out_path.exists():
        return True
    with out_path.open(newline="", encoding="utf-8") as handle:
        return next(csv.reader(handle), []) == FIELDS

def read_rows(source: Path, limit: int, offset: int, done: set[int]) -> list[tuple[int, str, str]]:
    with source.open(newline="", encoding="utf-8") as handle:
        all_rows = list(csv.DictReader(handle))
    pending = [
        (i, r["text"], r.get("label", ""))
        for i, r in enumerate(all_rows)
        if i >= offset and i not in done and r.get("text", "").strip()
    ]
    return pending[:limit]


async def build_rag_context(body: str, with_rag: bool) -> str:
    """Empty by default; with --with-rag, the same retrieval the real pipeline uses."""
    if not with_rag:
        return ""
    return format_rag_context(await retrieve(body, k=5))


async def evaluate_one(client: httpx.AsyncClient, url: str, body: str, with_rag: bool) -> dict[str, object]:
    resp = await client.post(
        f"{url}/process-email",
        # thread_context matches dashboard.py, which also sends "" — so rag_context is the
        # only variable between this harness and the production path.
        json={"thread_context": "", "email_body": body,
              "rag_context": await build_rag_context(body, with_rag)},
    )
    resp.raise_for_status()
    payload = resp.json()
    issues = payload.get("issues") or []
    return {
        "category": payload.get("category", ""),
        "confidence": payload.get("confidence"),
        "needs_human_review": payload.get("needs_human_review"),
        "attempts": payload.get("attempts"),
        "n_issues": len(issues),
        "issues": " | ".join(issues),
        "action_items": " | ".join(payload.get("action_items") or []),
        "error": "",
    }


TRANSPORT_ERRORS = ("ConnectError", "ReadError", "ReadTimeout", "ConnectTimeout")


async def agent_is_up(client: httpx.AsyncClient, url: str) -> bool:
    """Cheap reachability check — any HTTP answer means the service is serving."""
    try:
        await client.get(f"{url}/openapi.json", timeout=5.0)
    except httpx.HTTPError:
        return False
    return True


def stop_reason(error: str, url: str) -> str:
    """A suspended or stopped stack looks exactly like quota exhaustion. Say which it was."""
    if error.startswith(TRANSPORT_ERRORS):
        return (f"\n{url} stopped answering — check `make dev` is running and not suspended "
                "(Ctrl+Z leaves it holding the port but serving nothing). Nothing was charged.")
    return "\nthree consecutive failures — see the error column; re-run to continue"


def summarise(out_path: Path) -> None:
    if not out_path.exists():
        print("no results yet")
        return
    with out_path.open(newline="", encoding="utf-8") as handle:
        rows = [r for r in csv.DictReader(handle) if not r["error"]]
    if not rows:
        print("no successful rows recorded")
        return

    confidences = Counter(r["confidence"] for r in rows)
    print(f"\n{len(rows)} drafts evaluated — distinct confidence values: {len(confidences)}")
    for value, count in sorted(confidences.items(), key=lambda kv: float(kv[0] or 0)):
        print(f"   {value:<8} {'#' * count} ({count})")

    flagged = sum(1 for r in rows if r["needs_human_review"] == "True")
    burned = sum(int(r["attempts"] or 0) for r in rows)
    print(f"\nflagged for review: {flagged}/{len(rows)}")
    print(f"refine attempts across the run: {burned} (each is ~2 extra Gemini calls)")
    print(f"attempts distribution: {dict(Counter(r['attempts'] for r in rows))}")


def append_row(out_path: Path, row: dict[str, object]) -> None:
    """Open, append, close per row so a kill -9 still leaves every paid-for result on disk."""
    is_new = not out_path.exists()
    with out_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


async def run(args: argparse.Namespace) -> None:
    out_path = Path(args.out)
    if not columns_match(out_path):
        print(f"{out_path} has different columns — use a new --out")
        return
    done = load_done(out_path)
    rows = read_rows(Path(args.source), args.limit, args.offset, done)
    if not rows:
        print(f"nothing to do — {len(done)} rows already in {out_path}")
        return

    url = get_settings().email_agent_url.rstrip("/")
    print(f"{len(rows)} to evaluate against {url} ({len(done)} already done)")

    consecutive_failures = 0
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        if not await agent_is_up(client, url):
            print(f"agent at {url} is not answering — start it with `make dev` (or `make agent`)")
            return

        for position, (index, body, gold) in enumerate(rows, start=1):
            # Printed before the call, not after: one email can take a minute, and silence for
            # that long is indistinguishable from a hang.
            print(f"  [{position}/{len(rows)}] row {index} ...", end=" ", flush=True)
            try:
                result = await evaluate_one(client, url, body, args.with_rag)
                consecutive_failures = 0
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                # Excludes row/gold_label, which are merged in below: a blank `row` is
                # invisible to load_done, so a re-run would silently skip the failure.
                blanks = {k: "" for k in FIELDS if k not in ("row", "gold_label")}
                result = blanks | {"error": f"{type(exc).__name__}: {exc}"}
                consecutive_failures += 1

            append_row(out_path, {"row": index, "gold_label": gold, **result})
            print(f"confidence={result['confidence']} "
                  f"attempts={result['attempts']} {result['error']}".rstrip(), flush=True)

            if consecutive_failures >= CONSECUTIVE_FAILURE_LIMIT:
                print(stop_reason(str(result["error"]), url))
                break
            await asyncio.sleep(args.delay)

    summarise(out_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="CSV with a `text` column (e.g. holdout_to_label.csv)")
    parser.add_argument("--limit", type=int, default=20, help="emails to evaluate this run")
    parser.add_argument("--offset", type=int, default=0, help="skip the first N rows of the source")
    parser.add_argument("--out", default=None,
                        help="results CSV; defaults per condition so the two never mix")
    parser.add_argument("--with-rag", action="store_true",
                        help="send real retrieval context, as the production pipeline does")
    parser.add_argument("--delay", type=float, default=15.0,
                        help="seconds between emails; free-tier RPM is the binding limit")
    parser.add_argument("--summary-only", action="store_true", help="re-print the summary, no calls")
    args = parser.parse_args()
    # Separate files per condition: appending a rag run onto a no-rag file would let
    # load_done skip rows measured under the other condition and silently mix the two.
    args.out = args.out or ("critic_eval_rag.csv" if args.with_rag else "critic_eval.csv")

    if args.summary_only:
        summarise(Path(args.out))
        return
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
