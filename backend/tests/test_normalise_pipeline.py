"""Normalise each email once: language, English copy, deadline (specs/features/normalisation-v2.md)."""

import asyncio
from uuid import uuid4

import httpx
import pytest

from app.core.providers import Provider
from app.db.models import Message
from app.normalise import pipeline


@pytest.fixture
def agent(monkeypatch):
    state = {"sent": [], "status": None}

    async def call(_path, request, answer):
        state["sent"].append(request)
        if state["status"]:
            response = httpx.Response(state["status"], json={"detail": {"code": "x"}},
                                      request=httpx.Request("POST", "http://agent/translate"))
            raise httpx.HTTPStatusError("refused", request=response.request, response=response)
        return answer(language="en", text=f"EN {request.text}", egress=[])

    async def gemini(_user_id):
        return Provider.GEMINI

    async def nothing(*_args, **_kwargs):
        return None

    monkeypatch.setattr(pipeline.agent_client, "call", call)
    monkeypatch.setattr(pipeline.agent_client, "refusal_egress", lambda _response: [])
    monkeypatch.setattr(pipeline, "provider_for", gemini)
    monkeypatch.setattr(pipeline, "save_egress", nothing)
    return state


def _message(subject: str = "Permohonan cuti") -> Message:
    return Message(id=uuid4(), user_id=uuid4(), subject=subject)


def test_only_the_masked_own_text_is_sent_for_the_english_copy(agent):
    own = "Saya ingin memohon cuti, sila maklumkan [PERSON_1]."
    subject, body = asyncio.run(pipeline._english(_message(), own))
    assert (subject, body) == ("EN Permohonan cuti", f"EN {own}")
    assert [request.language for request in agent["sent"]] == ["en", "en"]


def test_a_refused_translation_leaves_no_copy_and_the_original_is_used(agent):
    agent["status"] = 422
    assert asyncio.run(pipeline._english(_message(), "Saya ingin cuti.")) == (None, None)


def test_an_agent_outage_keeps_the_email_in_the_queue(agent):
    agent["status"] = 503
    with pytest.raises(pipeline._TryAgainLater):
        asyncio.run(pipeline._english(_message(), "Saya ingin cuti."))


def test_private_mode_without_a_model_here_makes_no_copy_and_no_call(agent, monkeypatch):
    async def local(_user_id):
        return Provider.LOCAL

    monkeypatch.setattr(pipeline, "provider_for", local)
    monkeypatch.setattr(pipeline, "is_offered", lambda: False)
    assert asyncio.run(pipeline._english(_message(), "Saya ingin cuti.")) == (None, None)
    assert agent["sent"] == []


def test_a_long_text_is_cut_at_a_paragraph_within_the_agents_limit(monkeypatch):
    monkeypatch.setattr(pipeline, "MAX_TRANSLATE_CHARS", 30)
    assert pipeline._within_limit("First paragraph here.\n\nSecond paragraph is long.") == "First paragraph here."


def test_empty_own_text_does_not_call_translate(agent):
    subject, body = asyncio.run(pipeline._english(_message("Permohonan"), ""))
    assert subject == "EN Permohonan" and body is None
    assert len(agent["sent"]) == 1


def test_within_limit_prevents_splitting_placeholders(monkeypatch):
    text = "nospaceshere_[PERSON_1]_tail"
    cut_inside = text.find("PERSON") + 3
    monkeypatch.setattr(pipeline, "MAX_TRANSLATE_CHARS", cut_inside)
    result = pipeline._within_limit(text)
    assert result == "nospaceshere_"
    assert "[" not in result
