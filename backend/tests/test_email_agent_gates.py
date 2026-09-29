"""Offline tests for the review gate. No network: Presidio and Gemini are never called."""

import asyncio
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import email_agent
from email_agent import (
    build_review_reasons,
    clamp_confidence,
    has_redaction_placeholder,
    pii_verdict,
    strip_quoted,
    unaddressed_requests,
    unsupported_specifics,
)
from gemini_client import GeminiError, GeminiErrorCode


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


@pytest.mark.parametrize("draft, expected", [
    ("That is 4,409 lb gross.", []),  # a correct conversion of 2,000 kg
    ("That is 4,000 lb gross.", ["4000"]),  # a wrong one
    ("That is 2,010 kg gross.", ["2010"]),  # same unit, different figure
])
def test_a_unit_conversion_is_supported_only_when_it_is_right(draft, expected):
    assert unsupported_specifics(draft, "Gross weight 2,000 kg.") == expected


def test_a_european_written_figure_matches_its_source():
    assert unsupported_specifics("I will refund 18.400,00 in full.", SOURCE) == []


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


# ---------- Redaction placeholders reaching a draft ----------

@pytest.mark.parametrize("draft", [
    "Please call [PHONE_REDACTED] tomorrow.",
    "Dear [Redacted], thanks for your note.",
    "The invoice shows [REDACTED] as the due date.",
])
def test_every_redaction_marker_in_a_draft_is_flagged(draft):
    """The listener writes three marker shapes; a leak of any of them must reach review."""
    assert has_redaction_placeholder(draft)


def test_ordinary_brackets_are_not_a_redaction_marker():
    assert not has_redaction_placeholder("See [attached] and [Appendix B].")



# ---------- Router and extraction read structured replies ----------

@pytest.mark.parametrize("reply, expected", [
    ({"category": "COMPLEX"}, "COMPLEX"),
    ({"category": "SOMETHING_ELSE"}, "NA"),
    ("STANDARD", "NA"),
])
def test_router_trusts_only_a_known_category(monkeypatch, reply, expected):
    async def fake(*_args, **_kwargs):
        return reply

    monkeypatch.setattr(email_agent, "call_gemini", fake)
    assert asyncio.run(email_agent.route_email("", "Can we meet?")) == expected


def test_action_items_drop_blank_and_non_text_entries(monkeypatch):
    async def fake(*_args, **_kwargs):
        return {"action_items": ["Send the invoice", "", 42, "  "]}

    monkeypatch.setattr(email_agent, "call_gemini", fake)
    assert asyncio.run(email_agent.extract_actions("Please send the invoice.")) == ["Send the invoice"]


@pytest.mark.parametrize("code, status", [
    (GeminiErrorCode.DEADLINE_EXCEEDED, 504),
    (GeminiErrorCode.UNAVAILABLE, 503),
])
def test_a_gemini_failure_reaches_the_caller_as_a_coded_status(monkeypatch, code, status):
    async def failing(*_args, **_kwargs):
        raise GeminiError(code, "test")

    monkeypatch.setattr(email_agent, "call_gemini", failing)
    response = TestClient(email_agent.app).post("/process-email", json={
        "thread_context": "", "email_body": "Hi", "rag_context": ""})
    assert response.status_code == status
    assert response.json()["detail"] == code


# ---------- Signals from the email itself ----------

@pytest.mark.parametrize("body, expected", [
    ("Your mailbox is full. Verify your account at https://mail-fix.example to keep it.", True),
    ("Please send your OTP to www.secure-pay.example today.", True),
    ("Please reset your password before Friday.", False),  # no link
    ("The agenda is at https://intranet.example/agenda", False),  # no credential ask
])
def test_phishing_needs_a_credential_ask_beside_a_link(body, expected):
    assert email_agent.phishing_signal(body) is expected


def _request(rag_context: str = "Refunds take 14 days.") -> email_agent.ProcessEmailRequest:
    return email_agent.ProcessEmailRequest(thread_context="", email_body="Hi", rag_context=rag_context)


def test_an_ungrounded_reply_is_a_review_reason():
    reasons = email_agent.input_reasons(_request(rag_context="  "), False, None, "STANDARD")
    assert any("not grounded" in reason for reason in reasons)


def test_router_disagreement_is_a_review_reason():
    reasons = email_agent.input_reasons(_request(), True, "NA", "STANDARD")
    assert "routing models disagree: STANDARD vs NA" in reasons


def test_no_second_opinion_without_doubt(monkeypatch):
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "other-model")
    assert asyncio.run(email_agent.second_opinion(_request(), is_phishing=False)) is None


def test_doubt_asks_the_other_model(monkeypatch):
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "other-model")
    asked = []

    async def fake(*_args, models=None, **_kwargs):
        asked.append(models)
        return {"category": "NA"}

    monkeypatch.setattr(email_agent, "call_gemini", fake)
    assert asyncio.run(email_agent.second_opinion(_request(), is_phishing=True)) == "NA"
    assert asked == [["other-model"]]


# ---------- Translation faithfulness ----------

TRANSLATE_SOURCE = "Dear [Redacted], the invoice of RM 1,250.00 is due 30 September 2026."


def test_a_faithful_translation_passes():
    malay = "Kepada [Redacted], invois RM 1.250,00 perlu dibayar pada 30 September 2026."
    assert email_agent.translation_problems(TRANSLATE_SOURCE, malay) == []


def test_a_filled_in_redaction_is_caught():
    guessed = "Kepada Encik Ali, invois RM 1,250.00 perlu dibayar pada 30 September 2026."
    assert "redaction markers changed" in email_agent.translation_problems(TRANSLATE_SOURCE, guessed)


def test_a_changed_figure_is_caught():
    wrong = "Kepada [Redacted], invois RM 1,520.00 perlu dibayar pada 30 September 2026."
    problems = email_agent.translation_problems(TRANSLATE_SOURCE, wrong)
    assert any("1250" in problem for problem in problems)


def test_chinese_date_order_keeps_every_figure():
    chinese = "[Redacted]您好，金额为 RM 1,250.00 的发票须于 2026年9月30日 前支付。"
    assert email_agent.translation_problems(TRANSLATE_SOURCE, chinese) == []


def test_an_unfaithful_translation_is_refused_with_422(monkeypatch):
    async def fake(*_args, **_kwargs):
        return {"translation": "Kepada Ali, invois RM 99 perlu dibayar."}

    monkeypatch.setattr(email_agent, "call_gemini", fake)
    response = TestClient(email_agent.app).post(
        "/translate", json={"text": TRANSLATE_SOURCE, "language": "ms"})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "translation_unfaithful"


def test_an_unsupported_language_is_rejected_before_any_call():
    response = TestClient(email_agent.app).post("/translate", json={"text": "hi", "language": "fr"})
    assert response.status_code == 422


def test_a_hostile_huge_number_does_not_crash_the_figures_gate():
    assert unsupported_specifics("1" + "0" * 400 + " kg shipped.", SOURCE) == []


def test_a_failing_second_opinion_degrades_to_none(monkeypatch):
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "missing-model")

    async def failing(*_args, **_kwargs):
        raise GeminiError(GeminiErrorCode.UNAVAILABLE, "404")

    monkeypatch.setattr(email_agent, "call_gemini", failing)
    assert asyncio.run(email_agent.second_opinion(_request(), is_phishing=True)) is None
