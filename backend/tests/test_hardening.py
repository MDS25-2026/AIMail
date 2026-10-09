"""Limits on the routes that were unbounded, a deadline-derived agent timeout, and a drafting batch that
survives one bad email (epic #138 lines 34-37)."""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app import dashboard
from app.admin.app import rate_limit_refresh
from app.agent_client import AGENT_TIMEOUT_MARGIN_SECONDS, agent_timeout_seconds
from app.core.constants import MAX_QUERY_CHARS
from app.core.ratelimit import rate_limit_list, rate_limit_send
from tests.conftest import AUTH_HEADERS


@pytest.mark.parametrize("path", ["/emails", "/documents"])
def test_listing_is_rate_limited(api_client, monkeypatch, path):
    monkeypatch.setattr(rate_limit_list, "limit", 2)
    codes = [api_client.get(path, headers=AUTH_HEADERS).status_code for _ in range(3)]
    assert codes[-1] == 429


def test_sending_and_admin_refresh_have_their_own_limits():
    assert rate_limit_send.limit > 0 and rate_limit_refresh.limit > 0
    assert rate_limit_send.name != rate_limit_list.name


@pytest.mark.parametrize(("path", "field"), [("/search", "query"), ("/ask", "question")])
def test_a_typed_question_has_a_size_limit(api_client, path, field):
    response = api_client.post(path, json={field: "x" * (MAX_QUERY_CHARS + 1)}, headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_the_agent_timeout_follows_its_deadline(monkeypatch):
    monkeypatch.setenv("AGENT_DEADLINE_SECONDS", "150")
    from app.core.config import get_settings

    get_settings.cache_clear()
    assert agent_timeout_seconds() == 150 + AGENT_TIMEOUT_MARGIN_SECONDS


def test_one_failing_email_does_not_stop_the_drafting_batch(monkeypatch):
    bad, good = uuid4(), uuid4()
    drafted, released = [], []

    async def load(pk, _scope):
        if pk == bad:
            raise SQLAlchemyError("connection reset")
        return (pk,)

    async def generate(pk):
        drafted.append(pk)
        return dashboard.GenerationOutcome.STORED

    async def release(pk):
        released.append(pk)

    monkeypatch.setattr(dashboard, "_load_with_thread", load)
    monkeypatch.setattr(dashboard, "_generate_and_store", generate)
    monkeypatch.setattr(dashboard, "release_drafting", release)
    assert asyncio.run(dashboard._draft_claimed([bad, good])) == 1
    assert drafted == [good] and released == [bad, good]
