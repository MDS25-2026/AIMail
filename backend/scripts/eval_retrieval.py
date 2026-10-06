"""Run the retrieval eval set and report per-query + aggregate metrics (S4).

Usage (from backend/, needs a live DB + GEMINI_API_KEY and an ingested corpus):

    python scripts/eval_retrieval.py [scripts/eval_set.json]        # S3 baseline (raw query)
    python scripts/eval_retrieval.py [scripts/eval_set.json] --reformulate   # S5 (reformulated)

Run both and compare: reformulation (S5) should beat the baseline's MRR / precision on the
same eval set, especially on low-ranked queries.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag.eval import hit_rate, precision_at_k, reciprocal_rank, relevance_judgments
from app.rag.reformulate import reformulate
from app.rag.retrieve import retrieve

_DEFAULT = Path(__file__).resolve().parent / "eval_set.json"


async def main(path: Path, use_reformulation: bool) -> None:
    spec = json.loads(path.read_text())
    k, cases = spec["k"], spec["queries"]
    precisions, rrs, hits = [], [], 0
    mode = "reformulated (S5)" if use_reformulation else "baseline (S3)"
    print(f"queries={len(cases)} k={k}  mode={mode}\n")
    print(f"  {'hit':<4}{'rank':<6}{'p@k':<6}query")
    for case in cases:
        query = await reformulate(case["query"]) if use_reformulation else case["query"]
        judgments = relevance_judgments(await retrieve(query, k), case["relevant"])
        precisions.append(precision_at_k(judgments))
        rrs.append(reciprocal_rank(judgments))
        hits += int(hit_rate(judgments))
        rank = next((i + 1 for i, judged in enumerate(judgments) if judged), None)
        mark = "Y" if hit_rate(judgments) else "N"
        print(f"  {mark:<4}{(str(rank) if rank else '-'):<6}{precisions[-1]:<6.2f}{case['query'][:58]}")
    n = len(cases)
    print(f"\nhit_rate     = {hits / n:.3f}   (R03.2 target >= 0.90)")
    print(f"precision@{k}  = {sum(precisions) / n:.3f}")
    print(f"MRR          = {sum(rrs) / n:.3f}")


if __name__ == "__main__":
    positional = [a for a in sys.argv[1:] if not a.startswith("--")]
    eval_path = Path(positional[0]) if positional else _DEFAULT
    asyncio.run(main(eval_path, use_reformulation="--reformulate" in sys.argv))
