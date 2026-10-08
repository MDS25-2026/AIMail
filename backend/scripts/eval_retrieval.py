"""Measure retrieval on a labelled set (eval/retrieval), and calibrate the cutoff from it.

Usage (from backend/, needs the database and, for Gemini, GOOGLE_API_KEY; the set's corpus must be
ingested for the owner):

    python scripts/eval_retrieval.py --owner <uuid>                       # report at today's cutoff
    python scripts/eval_retrieval.py --owner <uuid> --calibrate           # record scores, pick the cutoff
    python scripts/eval_retrieval.py --owner <uuid> --provider local --calibrate
    python scripts/eval_retrieval.py --set eval/retrieval/v0.json --reformulate   # S5 against S3

--calibrate writes eval/retrieval/<set>.<provider>.scores.json (scores and judgments, no text) and
the chosen cutoff into app/rag/cutoffs.json. tests/test_retrieval_calibration.py replays the
recorded scores offline, so a cutoff that the evidence does not support fails CI.
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.ownership import LEGACY, Scope
from app.core.providers import Provider
from app.rag import calibration
from app.rag.calibration import Ranked
from app.rag.eval import reciprocal_rank, relevance_judgments, section_judgments
from app.rag.reformulate import reformulate
from app.rag.retrieve import CUTOFFS_FILE, cutoff_for, model_tag, search

BACKEND = Path(__file__).resolve().parent.parent
DEFAULT_SET = BACKEND / "eval" / "retrieval" / "v1.json"


def scores_file(set_path: Path, provider: Provider) -> Path:
    return set_path.with_name(f"{set_path.stem}.{provider}.scores.json")


def _judge(chunks: list, case: dict) -> list[bool]:
    if "sections" in case:
        return section_judgments(chunks, case["sections"])
    return relevance_judgments(chunks, case["markers"])


async def run(spec: dict, scope: Scope, provider: Provider, is_reformulated: bool) -> list[Ranked]:
    results = []
    for case in spec["queries"]:
        query = await reformulate(case["query"], provider=provider) if is_reformulated else case["query"]
        chunks = await search(query, spec["k"], scope=scope, provider=provider)
        results.append(Ranked(case["id"], case["language"], [c["similarity_score"] for c in chunks],
                              _judge(chunks, case)))
    return results


def report(results: list[Ranked], cutoff: float) -> None:
    print(f"cutoff {cutoff:.2f}\n  {'language':<10}{'n':<4}{'hit rate':<10}{'MRR':<8}F1")
    languages = sorted({result.language for result in results})
    for language in [*languages, "all"]:
        group = [r for r in results if language in ("all", r.language)]
        mrr = sum(reciprocal_rank(r.relevant) for r in group) / len(group)
        print(f"  {language:<10}{len(group):<4}{calibration.hit_rate(group, cutoff):<10.3f}{mrr:<8.3f}"
              f"{calibration.mean_f1(group, cutoff):.3f}")
    for result in results:
        if not any(result.relevant):
            print(f"  miss: {result.query_id} (no answering section in the top {len(result.relevant)})")


def record(results: list[Ranked], set_path: Path, spec: dict, provider: Provider) -> float:
    cutoff = calibration.best_cutoff(results)
    model = model_tag(provider)
    scores_file(set_path, provider).write_text(json.dumps({
        "eval_set": f"retrieval/v{spec['version']}", "model": model,
        "results": [{"id": r.query_id, "language": r.language, "scores": r.scores, "relevant": r.relevant}
                    for r in results],
    }, indent=2) + "\n")
    cutoffs = json.loads(CUTOFFS_FILE.read_text())
    cutoffs[provider] = {"cutoff": cutoff, "model": model, "eval_set": f"retrieval/v{spec['version']}",
                         "calibrated_on": datetime.now(timezone.utc).date().isoformat()}
    CUTOFFS_FILE.write_text(json.dumps(cutoffs, indent=2) + "\n")
    return cutoff


async def main(args: argparse.Namespace) -> None:
    spec = json.loads(args.set.read_text(encoding="utf-8"))
    provider = Provider(args.provider)
    scope = Scope(owner_id=args.owner) if args.owner else LEGACY
    results = await run(spec, scope, provider, args.reformulate)
    print(f"set=v{spec['version']} queries={len(results)} k={spec['k']} provider={provider} "
          f"model={model_tag(provider)}{' reformulated' if args.reformulate else ''}\n")
    if args.calibrate:
        report(results, record(results, args.set, spec, provider))
        print(f"\nwrote {scores_file(args.set, provider)} and {CUTOFFS_FILE}")
        return
    report(results, cutoff_for(provider, model_tag(provider)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--set", type=Path, default=DEFAULT_SET)
    parser.add_argument("--owner", type=UUID, help="the account whose documents are searched; omit for unowned")
    parser.add_argument("--provider", choices=[p.value for p in Provider], default=Provider.GEMINI.value)
    parser.add_argument("--calibrate", action="store_true")
    parser.add_argument("--reformulate", action="store_true")
    asyncio.run(main(parser.parse_args()))
