"""The model gateway (model_gateway.py) and the local client's parity with Gemini (local_client.py)."""

import asyncio

import httpx
import pytest

import local_client
import model_gateway
from app.core.providers import Provider
from model_runtime import ModelError, ModelErrorCode, track_calls
from tests.conftest import agent_client


@pytest.fixture
def sent(monkeypatch):
    calls = []

    async def gemini(prompt, **kwargs):
        calls.append(("gemini", prompt, kwargs))
        return "ok"

    async def local(prompt, **kwargs):
        calls.append(("local", prompt, kwargs))
        return "ok"

    monkeypatch.setattr(model_gateway, "gemini_generate", gemini)
    monkeypatch.setattr(model_gateway, "generate_local", local)
    return calls


@pytest.mark.parametrize("provider", list(Provider))
def test_each_provider_gets_only_its_own_calls(sent, provider):
    asyncio.run(model_gateway.generate("Hi [PERSON_1]", provider=provider, purpose="draft"))
    assert [call[0] for call in sent] == [provider.value]


def test_a_detail_that_slipped_past_masking_is_masked_before_it_leaves(sent):
    asyncio.run(model_gateway.generate("Reach me at aisyah@example.com or 012-345 6789",
                                       provider=Provider.GEMINI, purpose="refine"))
    prompt = sent[0][1]
    assert "aisyah@example.com" not in prompt and "012-345 6789" not in prompt


def test_the_rules_travel_as_the_system_message_and_are_checked_too(sent):
    asyncio.run(model_gateway.generate("email", provider=Provider.LOCAL, purpose="draft",
                                       system="Rules. Never write to x@y.com"))
    assert sent[0][2]["system"] == "Rules. Never write to [EMAIL_REDACTED]"


def test_every_prompt_that_leaves_is_recorded_without_its_text(sent):
    with model_gateway.track_egress() as egress:
        asyncio.run(model_gateway.generate("Hi [PERSON_1], call [PHONE_1] or 012-345 6789",
                                           provider=Provider.GEMINI, purpose="draft"))
    [record] = egress
    assert record["purpose"] == "draft" and record["provider"] == "gemini"
    assert record["hidden"] == {"person": 1, "phone": 1} and record["caught"] == 1
    assert set(record) == {"purpose", "provider", "chars", "sha256", "hidden", "caught"}  # no prompt text


def test_an_agent_request_without_a_provider_is_refused():
    response = agent_client().post("/process-email", json={"thread_context": "", "email_body": "Hi",
                                                           "rag_context": ""})
    assert response.status_code == 422


# ---------- the local client keeps Gemini's promises ----------

@pytest.fixture
def ollama(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_MODEL", "gemma4:e2b")
    seen = []

    def answer_with(body: dict):
        def respond(request: httpx.Request) -> httpx.Response:
            seen.append(request.read())
            return httpx.Response(200, json=body)
        monkeypatch.setattr(local_client, "transport", httpx.MockTransport(respond))

    return answer_with, seen


def test_a_cut_off_local_reply_is_never_passed_off_as_whole(ollama):
    answer_with, _seen = ollama
    answer_with({"message": {"content": "Dear team, as discussed we will"}, "done_reason": "length"})
    with pytest.raises(ModelError) as caught:
        asyncio.run(local_client.generate_local("Draft a reply", max_output_tokens=50))
    assert caught.value.code == ModelErrorCode.OUTPUT_TRUNCATED


def test_a_long_stage_keeps_its_own_output_budget(ollama):
    answer_with, seen = ollama
    answer_with({"message": {"content": "Terjemahan."}, "done_reason": "stop"})
    asyncio.run(local_client.generate_local("Translate", max_output_tokens=16_384, system="Rules"))
    body = seen[0].decode()
    assert '"num_predict":16384' in body.replace(" ", "") and '"role":"system"' in body.replace(" ", "")


def test_local_attempts_are_recorded_like_geminis(ollama):
    answer_with, _seen = ollama
    answer_with({"message": {"content": "Noted."}, "done_reason": "stop"})
    with track_calls() as calls:
        asyncio.run(local_client.generate_local("Hi"))
    assert [(call["provider"], call["outcome"]) for call in calls] == [("local", "ok")]
