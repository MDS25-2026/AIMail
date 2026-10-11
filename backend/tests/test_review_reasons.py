"""Review reasons as codes (app/review_reasons.py, specs/features/plain-wording-and-polish.md)."""

import pytest

from app.agent_contract import ReviewCode, ReviewReason
from app.review_reasons import review_reasons


@pytest.mark.parametrize(("text", "code", "items"), [
    ("confidence 0.4 below 0.8", ReviewCode.LOW_CONFIDENCE, []),
    ("does not address: Send the invoice; Confirm the date", ReviewCode.DOES_NOT_ADDRESS,
     ["Send the invoice", "Confirm the date"]),
    ("does not address everything asked", ReviewCode.INCOMPLETE, []),
    ("figures not in source: 1250, 30", ReviewCode.FIGURES_NOT_IN_SOURCE, ["1250", "30"]),
    ("pii: MY_NRIC, PERSON", ReviewCode.PII_FOUND, ["MY_NRIC", "PERSON"]),
    ("pii: PRESIDIO_UNAVAILABLE", ReviewCode.PII_SCAN_UNAVAILABLE, []),
    ("no policy context retrieved: reply is not grounded", ReviewCode.NOT_GROUNDED, []),
    ("no draft: gemini_output_truncated", ReviewCode.NO_DRAFT, []),
    ("needed 2 refine round(s)", ReviewCode.REFINE_ROUNDS, []),
])
def test_an_older_drafts_reasons_are_read_from_their_text(text, code, items):
    assert review_reasons({"review_reasons": [text]}) == [ReviewReason(code=code, items=items)]


def test_a_reason_no_pattern_knows_is_flagged_for_review_never_shown_raw():
    assert review_reasons({"review_reasons": ["something new the agent says"]}) == [
        ReviewReason(code=ReviewCode.UNKNOWN)]


def test_stored_codes_win_over_the_text():
    checks = {"review_reasons": ["confidence 0.4 below 0.8"],
              "review_codes": [{"code": "refine_rounds", "items": ["1"]}]}
    assert review_reasons(checks) == [ReviewReason(code=ReviewCode.REFINE_ROUNDS, items=["1"])]


def test_an_email_never_reviewed_has_no_reasons():
    assert review_reasons(None) == [] and review_reasons({}) == []
