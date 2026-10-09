"""Unit and integration tests for natural language inbox search & Q&A assistant (Issue #144)."""

import asyncio

from app.core.providers import Provider
from app.inbox_search import (
    InboxSearchRequest,
    InboxSearchResponse,
    SearchSource,
    SourceType,
    contextualize_query,
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

    resp = InboxSearchResponse(answer="Ground answer.", sources=[source])
    assert len(resp.sources) == 1
    assert resp.answer == "Ground answer."


def test_contextualize_query_empty_history() -> None:
    res = asyncio.run(contextualize_query("What was agreed?", [], Provider.GEMINI))
    assert res == "What was agreed?"


def test_inbox_search_unauthenticated_returns_401(api_client) -> None:
    resp = api_client.post("/api/search/inbox", json={"query": "test query"})
    assert resp.status_code == 401
