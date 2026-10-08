"""The labelled critic set (eval/critic) is well formed, and its deterministic part holds offline.

scripts/eval_critic_set.py measures the whole gate against a model; this replays only the figures
check, which needs neither a model nor Presidio, so a regression there fails CI.
"""

import json
from pathlib import Path

from app.core.language import Language
from email_agent import unsupported_specifics

SPEC = json.loads((Path(__file__).resolve().parent.parent / "eval" / "critic" / "v1.json").read_text(encoding="utf-8"))


def _sources(case: dict) -> tuple[str, str]:
    return case["email_body"], case["rag_context"]


def test_the_set_covers_every_failure_and_every_language():
    assert {case["failure"] for case in SPEC["cases"]} == set(SPEC["failures"])
    assert {case["language"] for case in SPEC["cases"]} == set(Language)
    assert all(case["should_flag"] == (case["failure"] != "none") for case in SPEC["cases"])


def test_every_invented_figure_is_caught_without_a_model():
    invented = [case for case in SPEC["cases"] if case["failure"] == "invented_figure"]
    assert all(unsupported_specifics(case["draft"], *_sources(case)) for case in invented)


def test_no_clean_draft_is_accused_of_inventing_a_figure():
    clean = [case for case in SPEC["cases"] if case["failure"] == "none"]
    assert all(unsupported_specifics(case["draft"], *_sources(case)) == [] for case in clean)
