"""Precision and recall of the review gate on hand-labelled drafts (eval/critic).

Each case is a draft with one planted failure, or none. The gate flags a draft when any review
reason fires (email_agent.build_review_reasons, as the agent decides it, without the email's own
signals); this reports how often it flags what it should, overall and per failure, and which check
caught each one.

Usage (from backend/, with Presidio up and the provider reachable):

    python scripts/eval_critic_set.py                      # Gemini, eval/critic/v1.json
    python scripts/eval_critic_set.py --provider local

The deterministic part (the figures check) is replayed offline in tests/test_critic_eval_set.py.
"""

import argparse
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agent_contract import DEFAULT_TONE_PROMPT
from app.core.providers import Provider
from email_agent import (
    PRESIDIO_UNAVAILABLE,
    Candidate,
    DraftContext,
    assess,
    build_review_reasons,
    using,
)
from model_runtime import deadline

DEFAULT_SET = Path(__file__).resolve().parent.parent / "eval" / "critic" / "v1.json"
NONE = "none"


def _context(case: dict) -> DraftContext:
    return DraftContext(thread_context="", rag_context=case["rag_context"], email_body=case["email_body"],
                        tone=DEFAULT_TONE_PROMPT, action_items=case["action_items"])


def _caught_by(reasons: list[str]) -> list[str]:
    """The check behind each reason, without the detail after its colon or the score."""
    return sorted({"low confidence" if reason.startswith("confidence") else reason.split(":", 1)[0]
                   for reason in reasons})


async def judge(case: dict) -> tuple[Candidate, list[str]]:
    with deadline():
        candidate = await assess(_context(case), case["draft"])
    if PRESIDIO_UNAVAILABLE in candidate.pii_findings:
        raise SystemExit("Presidio is not reachable: start it (make dev) before measuring")
    return candidate, build_review_reasons(candidate, 0)


def report(rows: list[tuple[dict, list[str]]]) -> None:
    flagged = [(case, bool(reasons)) for case, reasons in rows]
    true_pos = sum(case["should_flag"] and is_flagged for case, is_flagged in flagged)
    false_pos = sum(not case["should_flag"] and is_flagged for case, is_flagged in flagged)
    positives = sum(case["should_flag"] for case, _ in flagged)
    precision = true_pos / (true_pos + false_pos) if true_pos + false_pos else 0.0
    recall = true_pos / positives if positives else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    print(f"\nprecision {precision:.3f}  recall {recall:.3f}  F1 {f1:.3f}  "
          f"(flagged {true_pos + false_pos} of {len(rows)}; {positives} should be)\n")
    by_failure: Counter[str] = Counter(case["failure"] for case, _ in flagged)
    caught: Counter[str] = Counter(case["failure"] for case, is_flagged in flagged if is_flagged)
    for failure in sorted(by_failure):
        verb = "flagged (false alarms)" if failure == NONE else "caught"
        print(f"  {failure:<16}{caught[failure]}/{by_failure[failure]} {verb}")


async def main(set_path: Path, provider: Provider) -> None:
    spec = json.loads(set_path.read_text(encoding="utf-8"))
    rows = []
    print(f"set=v{spec['version']} cases={len(spec['cases'])} provider={provider}\n")
    print(f"  {'case':<26}{'flag':<6}{'conf':<6}caught by")
    with using(provider):
        for case in spec["cases"]:
            candidate, reasons = await judge(case)
            rows.append((case, reasons))
            confidence = "-" if candidate.confidence is None else f"{candidate.confidence:.2f}"
            print(f"  {case['id']:<26}{'Y' if reasons else 'N':<6}{confidence:<6}{', '.join(_caught_by(reasons))}")
    report(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--set", type=Path, default=DEFAULT_SET)
    parser.add_argument("--provider", choices=[p.value for p in Provider], default=Provider.GEMINI.value)
    arguments = parser.parse_args()
    asyncio.run(main(arguments.set, Provider(arguments.provider)))
