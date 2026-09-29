"""How long a draft takes end to end, and what the Gemini client had to do to get it.

Posts holdout emails at Lane C's /process-email (as eval_critic.py does) and times each one,
then summarises from the draft's own model_calls: p50/p95/max seconds, how many drafts would
overrun the dashboard's timeout, retries, and how often the fallback model answered. Prints no
email content. Each email costs about six Gemini calls, so N stays small by default.

Usage (from backend/, with the agent running on :8001):
    python scripts/latency.py holdout_to_label.csv --limit 10 [--with-rag]
"""

import argparse
import asyncio
import math
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval_critic import (
    REQUEST_TIMEOUT_SECONDS,
    agent_is_up,
    build_rag_context,
    read_rows,
)

from app.core.config import get_settings
from app.dashboard import AGENT_TIMEOUT_SECONDS

OK = "ok"


def percentile(values: list[float], share: float) -> float:
    """Nearest-rank percentile: always a value that was actually measured."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(share * len(ordered)) - 1)]


async def time_one(client: httpx.AsyncClient, url: str, body: str, with_rag: bool) -> dict:
    context = await build_rag_context(body, with_rag)
    started = time.perf_counter()
    response = await client.post(
        f"{url}/process-email",
        json={"thread_context": "", "email_body": body, "rag_context": context},
    )
    elapsed = time.perf_counter() - started
    calls = response.json().get("model_calls", []) if response.is_success else []
    models = [call["model"] for call in calls]
    return {
        "seconds": elapsed,
        "status": response.status_code,
        "attempts": len(calls),
        "retries": sum(1 for call in calls if call["outcome"] != OK),
        "used_fallback": len(set(models)) > 1,
    }


def summarise(results: list[dict]) -> str:
    seconds = [r["seconds"] for r in results]
    overruns = sum(1 for s in seconds if s >= AGENT_TIMEOUT_SECONDS)
    return "\n".join([
        f"drafts            {len(results)}  (failed: {sum(1 for r in results if r['status'] != 200)})",
        (f"seconds p50/p95   {percentile(seconds, 0.5):.1f} / {percentile(seconds, 0.95):.1f}"
         f"  max {max(seconds):.1f}"),
        f"over {AGENT_TIMEOUT_SECONDS}s timeout  {overruns}",
        f"gemini attempts   {sum(r['attempts'] for r in results) / len(results):.1f} per draft",
        f"retried attempts  {sum(r['retries'] for r in results)}",
        f"fallback answered {sum(1 for r in results if r['used_fallback'])} draft(s)",
    ])


async def run(args: argparse.Namespace) -> None:
    url = get_settings().email_agent_url.rstrip("/")
    rows = read_rows(Path(args.source), args.limit, 0, set())
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        if not await agent_is_up(client, url):
            sys.exit(f"{url} is not answering: start it with `make agent`. Nothing was charged.")
        results = []
        for index, (_, body, _) in enumerate(rows, 1):
            results.append(await time_one(client, url, body, args.with_rag))
            print(f"  {index}/{len(rows)}  {results[-1]['seconds']:.1f}s  {results[-1]['status']}")
    if results:
        print("\n" + summarise(results))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("source", help="CSV with a 'text' column of masked emails")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--with-rag", action="store_true", help="retrieve policy context too")
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
