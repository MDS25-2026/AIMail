"""Regenerate and refine report a draft the agent could not change, instead of answering 200 with the old one."""

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app import dashboard
from app.db.models import MaskingStatus, Message
from tests.conftest import AUTH_HEADERS as AUTH


def _message(**fields) -> Message:
    return Message(id=uuid4(), masking_status=MaskingStatus.COMPLETE, body_masked="Hi",
                   created_at=datetime(2026, 9, 30, tzinfo=timezone.utc), **fields)


@pytest.fixture
def loaded(monkeypatch):
    """Serve one message from the loaders, and stub the writes that need a database."""
    message = _message(draft_reply="Old draft")

    async def load(pk):
        return message

    async def load_with_thread(pk):
        return message, []

    async def nothing(*_args, **_kwargs):
        return None

    async def stored(pk, fields):
        return True

    monkeypatch.setattr(dashboard, "_load", load)
    monkeypatch.setattr(dashboard, "_load_with_thread", load_with_thread)
    monkeypatch.setattr(dashboard, "audit", nothing)
    monkeypatch.setattr(dashboard, "_update_unsent", stored)
    return message


def _generation_returns(monkeypatch, result: dict) -> None:
    async def generate(message, tone, thread):
        return result

    monkeypatch.setattr(dashboard, "_generate", generate)


def test_a_regenerate_the_agent_cannot_answer_is_an_error_not_the_old_draft(monkeypatch, loaded):
    _generation_returns(monkeypatch, {})
    with pytest.raises(dashboard.DraftNotUpdatedError) as caught:
        asyncio.run(dashboard.regenerate_email(str(loaded.id)))
    assert (caught.value.code, caught.value.status_code) == (dashboard.DraftErrorCode.AGENT_UNAVAILABLE, 502)
    assert loaded.draft_reply == "Old draft"


def test_a_regenerate_refused_for_content_is_an_error_and_keeps_the_draft(monkeypatch, loaded):
    _generation_returns(monkeypatch, dashboard._not_drafted("gemini_output_truncated"))
    with pytest.raises(dashboard.DraftNotUpdatedError) as caught:
        asyncio.run(dashboard.regenerate_email(str(loaded.id)))
    assert (caught.value.code, caught.value.status_code) == (dashboard.DraftErrorCode.DRAFT_REFUSED, 422)
    assert loaded.draft_reply == "Old draft"


def test_a_regenerate_judged_to_need_no_reply_is_not_an_error(monkeypatch, loaded):
    _generation_returns(monkeypatch, {"category": "NA", "draft": None, "summary": "", "action_items": []})
    email = asyncio.run(dashboard.regenerate_email(str(loaded.id)))
    assert email is not None and email.id == str(loaded.id)


def test_a_refine_the_agent_cannot_answer_is_an_error_not_the_old_draft(monkeypatch, loaded):
    async def unavailable(*_args):
        raise dashboard.DraftNotUpdatedError(dashboard.DraftErrorCode.AGENT_UNAVAILABLE, 502)

    monkeypatch.setattr(dashboard, "_refine", unavailable)
    with pytest.raises(dashboard.DraftNotUpdatedError) as caught:
        asyncio.run(dashboard.refine_email(str(loaded.id), "shorter", "Old draft"))
    assert (caught.value.code, caught.value.status_code) == (dashboard.DraftErrorCode.AGENT_UNAVAILABLE, 502)


def test_a_quarantined_message_cannot_be_refined(monkeypatch, loaded):
    loaded.masking_status = MaskingStatus.PENDING

    async def must_not_run(*_args):
        raise AssertionError("refine ran on a quarantined message")

    monkeypatch.setattr(dashboard, "_refine", must_not_run)
    with pytest.raises(dashboard.DraftNotUpdatedError) as caught:
        asyncio.run(dashboard.refine_email(str(loaded.id), "shorter", "Old draft"))
    assert (caught.value.code, caught.value.status_code) == (dashboard.DraftErrorCode.MASKING_PENDING, 409)


@pytest.fixture(autouse=True)
def _reset_limit():
    from app.core.ratelimit import rate_limit_generation

    rate_limit_generation.reset()
    yield
    rate_limit_generation.reset()


@pytest.mark.parametrize("path, target, body", [
    ("/emails/x/regenerate", "app.main.regenerate_email", {"tone": "professional"}),
    ("/emails/x/refine", "app.main.refine_email", {"instruction": "shorter", "draft": "Old draft"}),
])
def test_the_route_answers_the_errors_status_and_code(api_client, monkeypatch, path, target, body):
    async def unavailable(*_args, **_kwargs):
        raise dashboard.DraftNotUpdatedError(dashboard.DraftErrorCode.AGENT_UNAVAILABLE, 502)

    monkeypatch.setattr(target, unavailable)
    response = api_client.post(path, json=body, headers=AUTH)
    assert response.status_code == 502
    assert response.json()["detail"] == "agent_unavailable"
