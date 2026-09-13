"""Offline tests for the review gate. No network: Presidio and Gemini are never called."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from email_agent import (
    build_review_reasons,
    clamp_confidence,
    pii_verdict,
    strip_quoted,
    unaddressed_requests,
    unsupported_specifics,
)


@pytest.mark.parametrize("raw, expected", [
    ("Please review the deck.\n\n-----Original Message-----\nFrom: bob\nSend the invoice",
     "Please review the deck."),
    ("Can you confirm Friday?\nOn 2 May, Ali wrote:\n> please send the report",
     "Can you confirm Friday?"),
    ("Let me know what you think.", "Let me know what you think."),
])
def test_strips_quoted_history(raw, expected):
    assert strip_quoted(raw) == expected


def test_forward_with_no_comment_keeps_full_text():
    """Stripping would leave nothing, and an empty body extracts nothing rather than the wrong thing."""
    raw = "---------------------- Forwarded by Phillip\nFrom: Phillip\nCall Brian for a password"
    assert strip_quoted(raw) == raw.strip()


@pytest.mark.parametrize("value, expected", [
    (0.95, 0.95), (5.0, 1.0), (-2, 0.0), ("0.8", 0.8), (None, None), ("abc", None),
])
def test_confidence_is_clamped(value, expected):
    """A hostile email reaches the critic's prompt, so its number is not trusted."""
    assert clamp_confidence(value) == expected


@pytest.mark.parametrize("findings, expected", [
    ([], True),
    (["EMAIL_ADDRESS"], False),
    (["PRESIDIO_UNAVAILABLE"], None),
    (["PRESIDIO_UNAVAILABLE", "MY_NRIC"], False),
])
def test_unreachable_scanner_is_not_a_clean_bill(findings, expected):
    assert pii_verdict(findings) is expected


def test_clean_draft_needs_no_review():
    assert build_review_reasons({"grounding_ok": True, "completeness": True}, 0.95, 0, []) == []


def test_tone_alone_never_triggers_review():
    """Style is advisory: a correct, PII-clean, complete draft is not blocked on register."""
    reasons = build_review_reasons(
        {"grounding_ok": True, "completeness": True, "tone_match": False}, 1.0, 0, [])
    assert reasons == []


def test_a_refined_draft_always_reaches_a_human():
    reasons = build_review_reasons({"grounding_ok": True, "completeness": True}, 1.0, 1, [])
    assert any("refine" in r for r in reasons)


def test_pii_finding_triggers_review_even_at_full_confidence():
    reasons = build_review_reasons({"grounding_ok": True, "completeness": True}, 1.0, 0, ["MY_NRIC"])
    assert any("pii" in r for r in reasons)


def test_failed_grounding_triggers_review_even_at_full_confidence():
    """The gate the old code could never reach: high self-reported score, failed real check."""
    reasons = build_review_reasons({"grounding_ok": False, "completeness": True}, 1.0, 0, [])
    assert any("grounding" in r for r in reasons)


SOURCE = ("Please refund the 18,400.00 difference for invoice INV-2026-0831 within 30 days. "
          "Gifts above RM500 must be declared.")


@pytest.mark.parametrize("draft, expected", [
    ("I will refund 18,400.00 for INV-2026-0831 within 30 days.", []),
    ("I will refund 18,400.00 within 60 days.", ["60"]),
    ("Gifts above RM5,000 must be declared.", ["5000"]),
    ("I will refund 18400 for invoice INV-2026-0831.", []),
    ("Gifts above RM500 must be declared.", []),
])
def test_value_substitution_is_caught(draft, expected):
    """The hallucination class embeddings miss: the wrong number is topically identical."""
    assert unsupported_specifics(draft, SOURCE) == expected


def test_currency_prefixed_amounts_are_seen():
    """A word boundary cannot match between a letter and a digit, so RM500 was invisible."""
    assert unsupported_specifics("Gifts above RM9,999 apply.", SOURCE) == ["9999"]


def test_single_digits_are_prose_not_facts():
    assert unsupported_specifics("Thanks for your 2 questions and 3 points.", SOURCE) == []


def test_unsupported_figures_reach_the_reviewer():
    reasons = build_review_reasons({"grounding_ok": True, "completeness": True}, 1.0, 0, [], ["60"])
    assert any("not in source" in r for r in reasons)


ITEMS = ["Confirm the licence count", "Refund the difference", "Send the corrected paperwork"]


def test_unaddressed_indices_map_back_to_request_text():
    assert unaddressed_requests({"unaddressed_items": [2]}, ITEMS) == ["Refund the difference"]


@pytest.mark.parametrize("indices", [[0], [4], [-1], ["2"], [None]])
def test_out_of_range_indices_are_dropped_not_trusted(indices):
    """A hostile email reaches the critic's prompt, so its indices are not trusted either."""
    assert unaddressed_requests({"unaddressed_items": indices}, ITEMS) == []


def test_no_unaddressed_items_is_clean():
    assert unaddressed_requests({"unaddressed_items": []}, ITEMS) == []
    assert unaddressed_requests({}, ITEMS) == []


def test_unaddressed_requests_are_named_in_the_review_reason():
    """'Incomplete' is not actionable; 'did not address X' is."""
    reasons = build_review_reasons({"grounding_ok": True}, 1.0, 0, [], [],
                                   ["Refund the difference"])
    assert any("Refund the difference" in r for r in reasons)


def test_boolean_completeness_still_used_when_nothing_was_extracted():
    reasons = build_review_reasons({"grounding_ok": True, "completeness": False}, 1.0, 0, [], [], [])
    assert any("everything asked" in r for r in reasons)


def test_pathological_numeric_input_stays_linear():
    """CodeQL flagged the earlier pattern as polynomial-backtracking on '9' then many '0's.

    This text comes from an outside party, so a stall here is a denial of service on the
    agent. The bound is ~250x the measured time, so it catches a reintroduced blowup
    (minutes, at this length) without being timing-flaky.
    """
    import time
    hostile = "9" + "0" * 50_000 + "!"
    started = time.perf_counter()
    unsupported_specifics(hostile, SOURCE)
    assert time.perf_counter() - started < 1.0
