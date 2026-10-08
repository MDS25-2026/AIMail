"""The retrieval cutoff is whatever the recorded evidence supports, checked offline on every run.

scripts/eval_retrieval.py --calibrate records each question's scores and judgments, no text, and
writes the cutoff it chose. These tests replay that record: a hand-edited cutoff, or a record that
no longer clears the hit-rate target, fails CI without a database or a model.
"""

import json
from pathlib import Path

import pytest

from app.core.language import Language
from app.core.providers import Provider
from app.rag import calibration
from app.rag.calibration import Ranked
from app.rag.retrieve import CUTOFFS_FILE, _calibrations

EVAL_DIR = Path(__file__).resolve().parent.parent / "eval" / "retrieval"
# R03.2: at least one answering chunk kept for nine questions in ten.
HIT_RATE_TARGET = 0.9


def _recorded(provider: Provider) -> tuple[dict, list[Ranked]]:
    entry = json.loads(CUTOFFS_FILE.read_text())[provider]
    version = entry["eval_set"].removeprefix("retrieval/")
    record = json.loads((EVAL_DIR / f"{version}.{provider}.scores.json").read_text())
    results = [Ranked(r["id"], r["language"], r["scores"], r["relevant"]) for r in record["results"]]
    return record | {"cutoff": entry["cutoff"], "cutoff_model": entry["model"]}, results


@pytest.mark.parametrize("provider", list(Provider))
def test_the_committed_cutoff_is_the_one_the_recorded_scores_choose(provider):
    record, results = _recorded(provider)
    assert record["model"] == record["cutoff_model"]
    assert calibration.best_cutoff(results) == record["cutoff"]


@pytest.mark.parametrize("provider", list(Provider))
def test_the_committed_cutoff_meets_the_hit_rate_target(provider):
    record, results = _recorded(provider)
    assert calibration.hit_rate(results, record["cutoff"]) >= HIT_RATE_TARGET


def test_private_mode_is_measured_in_all_three_languages():
    _record, results = _recorded(Provider.LOCAL)
    assert {result.language for result in results} == set(Language)


def test_every_cutoff_entry_loads():
    assert set(_calibrations()) == set(Provider)


# v1.json is a set; v1.local.scores.json is what a calibration recorded from it.
SETS = sorted(path for path in EVAL_DIR.glob("v*.json") if path.name.count(".") == 1)


@pytest.mark.parametrize("path", SETS, ids=lambda path: path.name)
def test_an_eval_set_is_well_formed(path):
    spec = json.loads(path.read_text())
    ids = [case["id"] for case in spec["queries"]]
    assert len(ids) == len(set(ids)) and spec["k"] > 0
    for case in spec["queries"]:
        assert case["language"] in set(Language) and case["query"].strip()
        assert case.get("sections") or case.get("markers")


# ---------- the choice itself ----------

def _ranked(scores: list[float], relevant: list[bool]) -> Ranked:
    return Ranked("q", "en", scores, relevant)


def test_a_cutoff_keeps_hits_close_to_the_best_one():
    assert calibration.kept(_ranked([0.8, 0.76, 0.6], [True, True, False]), 0.9) == [True, True, False]


def test_the_cutoff_that_drops_only_the_unrelated_chunk_wins():
    results = [_ranked([0.8, 0.76, 0.6], [True, True, False])]
    assert calibration.f1(results[0], calibration.best_cutoff(results)) == 1.0


def test_a_tie_goes_to_the_lower_cutoff_which_keeps_more():
    results = [_ranked([0.8], [True])]
    assert calibration.best_cutoff(results) == calibration.GRID[0]


def test_a_question_with_nothing_relevant_scores_zero_at_any_cutoff():
    result = _ranked([0.8, 0.7], [False, False])
    assert {calibration.f1(result, cutoff) for cutoff in calibration.GRID} == {0.0}
