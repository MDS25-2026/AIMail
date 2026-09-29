"""Offline tests for the agent's Gemini client. The network is an httpx.MockTransport."""

import asyncio
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gemini_client
from gemini_client import (
    CircuitBreaker,
    GeminiError,
    GeminiErrorCode,
    deadline,
    gemini_payload,
    generate,
    models_in_order,
)

PRIMARY = "primary-model"
FALLBACK = "fallback-model"


def reply(text: str, finish: str = "STOP") -> dict:
    return {"candidates": [{"finishReason": finish, "content": {"parts": [{"text": text}]}}]}


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    """Fresh breakers, no real sleeping, and a known primary/fallback pair for every test."""
    monkeypatch.setattr(gemini_client, "_breakers", {})
    monkeypatch.setenv("GEMINI_AGENT_MODEL", PRIMARY)
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", FALLBACK)

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(gemini_client.asyncio, "sleep", no_sleep)


def route(monkeypatch, handler) -> list[str]:
    """Serve requests with `handler(model)`; return the models asked, in order."""
    asked: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        model = request.url.path.rsplit("/", 1)[-1].split(":")[0]
        asked.append(model)
        return handler(model)

    monkeypatch.setattr(gemini_client, "transport", httpx.MockTransport(respond))
    return asked


def run(coro):
    return asyncio.run(coro)


def test_output_cap_reaches_the_gemini_request():
    payload = gemini_payload("hello", max_output_tokens=200)
    assert payload["generationConfig"]["maxOutputTokens"] == 200


def test_no_cap_leaves_the_request_uncapped():
    assert "maxOutputTokens" not in gemini_payload("hello")["generationConfig"]


def test_schema_requests_json():
    config = gemini_payload("hi", response_schema={"type": "object"})["generationConfig"]
    assert config["responseMimeType"] == "application/json"


def test_healthy_primary_answers_without_touching_the_fallback(monkeypatch):
    asked = route(monkeypatch, lambda model: httpx.Response(200, json=reply("fine")))
    assert run(generate("hi")) == "fine"
    assert asked == [PRIMARY]


def test_server_errors_are_retried_then_the_fallback_answers(monkeypatch):
    asked = route(monkeypatch, lambda model: httpx.Response(503) if model == PRIMARY
                  else httpx.Response(200, json=reply("from fallback")))
    assert run(generate("hi")) == "from fallback"
    assert asked == [PRIMARY] * gemini_client.ATTEMPTS_PER_MODEL + [FALLBACK]


def test_a_client_error_is_not_retried(monkeypatch):
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "")
    asked = route(monkeypatch, lambda model: httpx.Response(400))
    with pytest.raises(GeminiError) as caught:
        run(generate("hi"))
    assert caught.value.code == GeminiErrorCode.UNAVAILABLE
    assert asked == [PRIMARY]


def test_a_rate_limit_is_retried_on_the_same_model(monkeypatch):
    answers = iter([httpx.Response(429), httpx.Response(200, json=reply("ok"))])
    asked = route(monkeypatch, lambda model: next(answers))
    assert run(generate("hi")) == "ok"
    assert asked == [PRIMARY, PRIMARY]


def test_a_truncated_reply_is_refused_not_passed_off_as_whole(monkeypatch):
    route(monkeypatch, lambda model: httpx.Response(200, json=reply("half a sen", "MAX_TOKENS")))
    with pytest.raises(GeminiError) as caught:
        run(generate("hi", max_output_tokens=5))
    assert caught.value.code == GeminiErrorCode.OUTPUT_TRUNCATED


def test_a_blocked_reply_is_a_typed_error(monkeypatch):
    route(monkeypatch, lambda model: httpx.Response(200, json={"candidates": []}))
    with pytest.raises(GeminiError) as caught:
        run(generate("hi"))
    assert caught.value.code == GeminiErrorCode.NO_CANDIDATE


def test_schema_reply_comes_back_parsed(monkeypatch):
    route(monkeypatch, lambda model: httpx.Response(200, json=reply('{"category": "NA"}')))
    assert run(generate("hi", response_schema={"type": "object"})) == {"category": "NA"}


def test_a_spent_deadline_stops_before_calling(monkeypatch):
    asked = route(monkeypatch, lambda model: httpx.Response(200, json=reply("late")))

    async def late() -> None:
        with deadline(0):
            await generate("hi")

    with pytest.raises(GeminiError) as caught:
        run(late())
    assert caught.value.code == GeminiErrorCode.DEADLINE_EXCEEDED
    assert asked == []


def test_an_open_breaker_sends_calls_straight_to_the_fallback(monkeypatch):
    asked = route(monkeypatch, lambda model: httpx.Response(200, json=reply(model)))
    breaker = gemini_client.breaker_for(PRIMARY)
    for _ in range(breaker.threshold):
        breaker.record_failure()
    assert run(generate("hi")) == FALLBACK
    assert asked == [FALLBACK]


def test_the_last_model_is_tried_even_with_its_breaker_open(monkeypatch):
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "")
    asked = route(monkeypatch, lambda model: httpx.Response(200, json=reply("still here")))
    breaker = gemini_client.breaker_for(PRIMARY)
    for _ in range(breaker.threshold):
        breaker.record_failure()
    assert run(generate("hi")) == "still here"
    assert asked == [PRIMARY]


def test_breaker_half_opens_after_cooldown():
    now = [0.0]
    breaker = CircuitBreaker(threshold=2, cooldown=10, clock=lambda: now[0])
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.is_open()
    now[0] = 11
    assert not breaker.is_open()


def test_fallback_equal_to_primary_is_ignored(monkeypatch):
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", PRIMARY)
    assert models_in_order() == [PRIMARY]


def test_every_attempt_is_tracked_with_its_outcome(monkeypatch):
    answers = iter([httpx.Response(503), httpx.Response(200, json=reply("ok"))])
    route(monkeypatch, lambda model: next(answers))

    async def tracked() -> list[dict]:
        with gemini_client.track_calls() as calls:
            await generate("hi")
        return calls

    calls = run(tracked())
    assert [(c["model"], c["outcome"]) for c in calls] == [(PRIMARY, "http_503"), (PRIMARY, "ok")]
    assert all(isinstance(c["ms"], int) for c in calls)


def test_a_models_override_asks_only_that_model(monkeypatch):
    asked = route(monkeypatch, lambda model: httpx.Response(200, json=reply("x")))
    run(generate("hi", models=[FALLBACK]))
    assert asked == [FALLBACK]
