"""The backend's agent client (app/agent_client.py): typed requests, validated answers."""

import asyncio

import httpx
import pytest
from pydantic import ValidationError

from app import agent_client
from app.agent_contract import (
    TONE_PROMPTS,
    ProcessEmailRequest,
    ProcessEmailResponse,
    Tone,
)
from app.core.providers import Provider

REQUEST = ProcessEmailRequest(thread_context="", email_body="Hi", rag_context="", provider=Provider.GEMINI,
                              tone=TONE_PROMPTS[Tone.CASUAL])


@pytest.fixture
def agent(monkeypatch, test_settings):
    def answer_with(handler):
        monkeypatch.setattr(agent_client, "_client",
                            httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    return answer_with


def test_the_request_goes_as_the_shared_model_and_the_answer_comes_back_validated(agent):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.read())
        return httpx.Response(200, json={"category": "STANDARD", "summary": "s", "draft": "Hi."})

    agent(handler)
    answer = asyncio.run(agent_client.call("/process-email", REQUEST, ProcessEmailResponse))
    assert answer.draft == "Hi." and b'"provider":"gemini"' in seen[0].replace(b" ", b"")


def test_a_malformed_answer_fails_loudly_instead_of_reading_as_empty(agent):
    agent(lambda _request: httpx.Response(200, json={"draft": 42}))
    with pytest.raises(ValidationError):
        asyncio.run(agent_client.call("/process-email", REQUEST, ProcessEmailResponse))


def test_an_agent_that_is_restarting_is_tried_once_more(agent, monkeypatch):
    attempts = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) == 1:
            raise httpx.ConnectError("refused", request=request)
        return httpx.Response(200, json={"category": "NA", "summary": ""})

    async def no_wait(_seconds):
        return None

    monkeypatch.setattr(agent_client.asyncio, "sleep", no_wait)
    agent(handler)
    assert asyncio.run(agent_client.call("/process-email", REQUEST, ProcessEmailResponse)).category == "NA"
    assert len(attempts) == 2
