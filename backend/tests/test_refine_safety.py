"""A refined draft gets the same checks as a generated one, and typed text is masked before a model.

Refine used to return the model's text unchecked while the old critic verdict stayed on screen, and
the draft and instruction the user typed went to Gemini with any phone number or IC in them.
"""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import email_agent
from app import dashboard
from app.core.ownership import EVERYTHING
from app.core.providers import Provider
from app.core.typed_text import mask_typed_text
from app.db.models import MaskingStatus, Message
from tests.conftest import AUTH_HEADERS, agent_client

# ---------- Masking what the user typed ----------


@pytest.mark.parametrize("text, token", [
    ("mail me at aisyah.rahman@corp.com.my", "[EMAIL_REDACTED]"),
    ("call 012-345 6789 after lunch", "[PHONE_REDACTED]"),
    ("or +65 9123 4567 in Singapore", "[PHONE_REDACTED]"),
    ("her IC is 900101-14-5678", "[IC_REDACTED]"),
    ("passport A12345678 expires soon", "[PASSPORT_REDACTED]"),
    ("card 4111 1111 1111 1111 on file", "[CARD_REDACTED]"),
])
def test_fixed_format_details_are_masked(text, token):
    masked = mask_typed_text(text)
    assert token in masked


def test_names_amounts_dates_and_order_numbers_are_left_alone():
    text = "Hi Aisyah, the RM 1,250.00 invoice for order 12345678 is due 15/10/2026 at 3pm."
    assert mask_typed_text(text) == text


def test_a_long_reference_number_that_fails_the_card_checksum_is_not_a_card():
    assert mask_typed_text("ref 1234 5678 9012 3456") == "ref 1234 5678 9012 3456"


# ---------- The agent checks a refined draft ----------


def _stub_agent(monkeypatch, revised: str, evaluation: dict, pii: list[str]):
    async def llm(*_args, **_kwargs):
        return revised

    async def critic(*_args, **_kwargs):
        return evaluation

    async def scan(_draft):
        return pii

    monkeypatch.setattr(email_agent, "call_llm", llm)
    monkeypatch.setattr(email_agent, "evaluate_reply", critic)
    monkeypatch.setattr(email_agent, "scan_draft_pii", scan)


GOOD = {"confidence": 0.92, "grounding_ok": True, "pii_clean": True, "tone_match": True,
        "completeness": True, "issues": [], "unaddressed_items": []}


def _refine(body: dict):
    payload = {"email_body": "Can you confirm Friday?", "draft": "Friday works.",
               "instruction": "shorter", "thread_context": "", "rag_context": "Claims are paid within 30 days.",
               "action_items": ["Confirm Friday"], "provider": "gemini"} | body
    return agent_client().post("/refine", json=payload)


def test_a_clean_refined_draft_comes_back_with_its_checks(monkeypatch):
    _stub_agent(monkeypatch, "Friday is fine.", GOOD, [])
    body = _refine({}).json()
    assert body["draft"] == "Friday is fine."
    assert body["confidence"] == 0.92 and body["needs_human_review"] is False
    assert body["review_reasons"] == []


def test_a_refined_draft_keeps_the_reasons_the_email_itself_gives(monkeypatch):
    # Refine used to drop these: refining an ungrounded or phishing email cleared its warning.
    _stub_agent(monkeypatch, "Friday is fine.", GOOD, [])
    reasons = _refine({"rag_context": ""}).json()["review_reasons"]
    assert any("not grounded" in reason for reason in reasons)


def test_a_refined_draft_that_leaks_or_invents_is_flagged(monkeypatch):
    _stub_agent(monkeypatch, "Friday is fine, call 012-3456789. The fee is RM 9,999.", GOOD,
                ["MY_PHONE"])
    body = _refine({}).json()
    assert body["needs_human_review"] is True
    reasons = " ".join(body["review_reasons"])
    assert "pii: MY_PHONE" in reasons and "9999" in reasons


def test_figures_the_user_typed_into_the_draft_are_not_called_invented(monkeypatch):
    _stub_agent(monkeypatch, "The fee is RM 450.", GOOD, [])
    body = _refine({"draft": "Fee: RM 450, see you Friday."}).json()
    assert body["unsupported_specifics"] == []


# ---------- The backend sends masked text and stores the verdict ----------


@pytest.fixture
def backend(monkeypatch):
    message = Message(id=uuid4(), masking_status=MaskingStatus.COMPLETE, body_masked="Confirm Friday?",
                      draft_reply="Old draft", action_items=["Confirm Friday"],
                      rag_sources=[{"label": "Leave policy", "excerpt": "Leave needs 3 days notice."}],
                      critic_confidence=0.95, needs_human_review=False,
                      created_at=datetime(2026, 10, 4, tzinfo=timezone.utc))
    state = {"payload": None, "writes": None, "agent": {"draft": "New draft", "confidence": 0.4,
             "needs_human_review": True, "review_reasons": ["confidence 0.4 below 0.8"],
             "grounding_ok": True, "pii_findings": []}}

    async def load_with_thread(pk, scope):
        return message, []

    async def call_agent(path, request, _answer=None):
        state["payload"] = request.model_dump(mode="json")
        if isinstance(state["agent"], Exception):
            raise state["agent"]
        return state["agent"]

    async def update(pk, fields):
        state["writes"] = fields
        return True

    async def nothing(*_args, **_kwargs):
        return None

    for name, value in (("_load_with_thread", load_with_thread), ("_call_agent", call_agent),
                        ("_update_unsent", update), ("audit", nothing)):
        monkeypatch.setattr(dashboard, name, value)
    return message, state


def test_typed_text_reaches_the_agent_masked_with_the_context_the_critic_needs(backend):
    message, state = backend
    asyncio.run(dashboard.refine_email(str(message.id), "add my number 012-345 6789",
                                       "Reach me at a.b@corp.com", scope=EVERYTHING))
    payload = state["payload"]
    assert "012-345 6789" not in payload["instruction"] and "a.b@corp.com" not in payload["draft"]
    assert payload["action_items"] == ["Confirm Friday"]
    assert "Leave needs 3 days notice." in payload["rag_context"]


def test_the_refined_drafts_own_verdict_replaces_the_old_one(backend):
    message, state = backend
    asyncio.run(dashboard.refine_email(str(message.id), "shorter", "Old draft", scope=EVERYTHING))
    assert state["writes"]["draft_reply"] == "New draft"
    assert state["writes"]["critic_confidence"] == 0.4
    assert state["writes"]["needs_human_review"] is True


def test_a_refine_the_model_refused_is_reported_as_refused(backend):
    message, state = backend
    request = httpx.Request("POST", "http://agent/refine")
    state["agent"] = httpx.HTTPStatusError("422", request=request,
                                           response=httpx.Response(422, request=request))
    with pytest.raises(dashboard.DraftNotUpdatedError) as caught:
        asyncio.run(dashboard.refine_email(str(message.id), "shorter", "Old draft", scope=EVERYTHING))
    assert caught.value.code == dashboard.ErrorCode.DRAFT_REFUSED


# ---------- Questions typed into search and ask ----------


@pytest.fixture
def captured_query(monkeypatch):
    seen = {}

    async def retrieve(query, k, scope, provider):
        seen["query"] = query
        return []

    async def answer(question, chunks, provider):
        seen["question"] = question
        return "ok"

    async def gemini(_user_id):
        return Provider.GEMINI

    monkeypatch.setattr("app.main.retrieve", retrieve)
    monkeypatch.setattr("app.main.answer", answer)
    monkeypatch.setattr("app.main.provider_for", gemini)
    return seen


def test_a_search_query_is_masked_before_it_is_embedded(api_client, captured_query):
    api_client.post("/search", json={"query": "leave for IC 900101-14-5678"}, headers=AUTH_HEADERS)
    assert "900101-14-5678" not in captured_query["query"]


def test_an_ask_question_is_masked_before_it_reaches_the_model(api_client, captured_query):
    api_client.post("/ask", json={"question": "call 012-345 6789 about leave?"}, headers=AUTH_HEADERS)
    assert "012-345 6789" not in captured_query["question"]
