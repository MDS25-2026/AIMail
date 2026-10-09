"""Unit and integration tests for natural language inbox search & Q&A assistant (Issue #144)."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.core.providers import Provider
from app.inbox_search import (
    InboxSearchRequest,
    InboxSearchResponse,
    QueryIntent,
    SearchSource,
    SourceType,
    classify_intent_deterministic,
    contextualize_query,
    extract_sender_candidates,
    format_email_snippet,
    format_received_date,
    route_query_intent,
)


def test_inbox_search_models() -> None:
    req = InboxSearchRequest(query="pricing discounts")
    assert req.query == "pricing discounts"
    assert req.k_emails == 5
    assert req.k_docs == 3
    assert req.history == []

    # Source formatting
    source = SearchSource(
        source_type=SourceType.EMAIL,
        id="123e4567-e89b-12d3-a456-426614174000",
        title="Test subject",
        subtitle="Sender · Date",
        snippet="Snippet content",
    )
    assert source.source_type == "email"
    assert source.id == "123e4567-e89b-12d3-a456-426614174000"

    resp = InboxSearchResponse(
        answer="Ground answer.",
        sources=[source],
        has_restored_pii=True,
        intent=QueryIntent.EMAIL_SEARCH.value,
    )
    assert len(resp.sources) == 1
    assert resp.answer == "Ground answer."
    assert resp.has_restored_pii is True
    assert resp.intent == "email_search"


def test_classify_intent_deterministic_overview() -> None:
    # High-frequency user queries from live testing
    assert classify_intent_deterministic("whats in my inbox") == QueryIntent.INBOX_OVERVIEW
    assert classify_intent_deterministic("what's in my inbox") == QueryIntent.INBOX_OVERVIEW
    assert classify_intent_deterministic("tell me about the inbox") == QueryIntent.INBOX_OVERVIEW
    assert classify_intent_deterministic("tell me about my inbox") == QueryIntent.INBOX_OVERVIEW
    assert classify_intent_deterministic("tell me about my recent emails") == QueryIntent.INBOX_OVERVIEW
    assert classify_intent_deterministic("tell me about recent emails") == QueryIntent.INBOX_OVERVIEW
    assert classify_intent_deterministic("what are my recent emails") == QueryIntent.INBOX_OVERVIEW
    assert classify_intent_deterministic("what are the contents of my recent emails") == QueryIntent.INBOX_OVERVIEW
    assert classify_intent_deterministic("what emails are in my inbox") == QueryIntent.INBOX_OVERVIEW
    assert classify_intent_deterministic("summarize my inbox") == QueryIntent.INBOX_OVERVIEW
    assert classify_intent_deterministic("summarize my recent emails") == QueryIntent.INBOX_OVERVIEW
    assert classify_intent_deterministic("what emails do i have") == QueryIntent.INBOX_OVERVIEW
    assert classify_intent_deterministic("recent emails") == QueryIntent.INBOX_OVERVIEW
    assert classify_intent_deterministic("latest emails") == QueryIntent.INBOX_OVERVIEW
    assert classify_intent_deterministic("any new emails?") == QueryIntent.INBOX_OVERVIEW
    assert classify_intent_deterministic("give me an overview of my recent emails") == QueryIntent.INBOX_OVERVIEW
    assert classify_intent_deterministic("show my latest emails") == QueryIntent.INBOX_OVERVIEW


def test_classify_intent_deterministic_policy() -> None:
    assert classify_intent_deterministic("company policy on expenses") == QueryIntent.POLICY_QA
    assert classify_intent_deterministic("what is the remote work policy?") == QueryIntent.POLICY_QA
    assert classify_intent_deterministic("leave policy guidelines") == QueryIntent.POLICY_QA


def test_classify_intent_deterministic_fallback_to_none() -> None:
    # Specific targeted queries defer to Tier 2 LLM router
    assert classify_intent_deterministic("tell me about dr. asad's email") is None
    assert classify_intent_deterministic("did Bryan send the budget deck?") is None
    assert classify_intent_deterministic("Grab receipts for October") is None


def test_route_query_intent_fast_path() -> None:
    # Tier 1 fast path should resolve without calling model gateway
    resolved = asyncio.run(route_query_intent("whats in my inbox", Provider.GEMINI))
    assert resolved == QueryIntent.INBOX_OVERVIEW


def test_classify_intent_llm_mocked(monkeypatch) -> None:
    from app import inbox_search
    from app.inbox_search import classify_intent_llm

    async def mock_generate(prompt, **kwargs):
        user_query = prompt.split("Query:")[1].split("Respond with")[0].strip().lower()
        if "expense" in user_query or "policy" in user_query:
            return "POLICY_QA"
        if "status" in user_query or "yesterday" in user_query:
            return "INBOX_OVERVIEW"
        return "EMAIL_SEARCH"

    monkeypatch.setattr(inbox_search.model_gateway, "generate", mock_generate)

    res1 = asyncio.run(classify_intent_llm("Can I expense lunch?", Provider.GEMINI))
    assert res1 == QueryIntent.POLICY_QA

    res2 = asyncio.run(classify_intent_llm("status update from yesterday", Provider.GEMINI))
    assert res2 == QueryIntent.INBOX_OVERVIEW

    res3 = asyncio.run(classify_intent_llm("find the invoice from Bryan", Provider.GEMINI))
    assert res3 == QueryIntent.EMAIL_SEARCH


def test_extract_sender_candidates() -> None:
    assert extract_sender_candidates("tell me about dr. asad's email") == ["asad"]
    assert extract_sender_candidates("any emails from Bryan?") == ["bryan"]
    assert extract_sender_candidates("what about the reimbursement policy?") == ["reimbursement", "policy"]


def test_contextualize_query_empty_history() -> None:
    res = asyncio.run(contextualize_query("What was agreed?", [], Provider.GEMINI))
    assert res == "What was agreed?"


def test_inbox_search_unauthenticated_returns_401(api_client) -> None:
    resp = api_client.post("/api/search/inbox", json={"query": "test query"})
    assert resp.status_code == 401


def test_format_helpers() -> None:
    dt = datetime(2026, 10, 8, 14, 30, tzinfo=timezone.utc)
    formatted = format_received_date(dt)
    assert "08 Oct 2026" in formatted

    assert format_received_date(None) == "Unknown date"

    mock_msg = MagicMock()
    mock_msg.body_masked = "Short body"
    mock_msg.snippet_masked = None
    assert format_email_snippet(mock_msg) == "Short body"

    mock_msg.body_masked = "a" * 350
    assert len(format_email_snippet(mock_msg)) <= 280
    assert format_email_snippet(mock_msg).endswith("...")
