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
