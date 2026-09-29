"""Gemini calls for the Lane C agent: one deadline per draft, retries, a fallback model, a breaker.

Every stage of a draft (route, summarise, draft, critique, refine) shares one deadline, so a draft
that cannot finish fails here with a reason instead of at the dashboard's HTTP timeout with none.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import random
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import StrEnum

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-3.5-flash-lite"
# Greedy decoding for reproducibility. Reduces sampling randomness; does not guarantee determinism.
TEMPERATURE = 0.0
ATTEMPT_TIMEOUT_SECONDS = 30.0
# Below the dashboard's AGENT_TIMEOUT_SECONDS (app/dashboard.py), with room for retrieval first.
DEFAULT_DEADLINE_SECONDS = 100.0
ATTEMPTS_PER_MODEL = 3
BACKOFF_BASE_SECONDS = 2.0
BACKOFF_CAP_SECONDS = 10.0
RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})
BREAKER_THRESHOLD = 3
BREAKER_COOLDOWN_SECONDS = 60.0
FINISH_TRUNCATED = "MAX_TOKENS"

# Tests swap this for httpx.MockTransport; production leaves it None.
transport: httpx.AsyncBaseTransport | None = None


class GeminiErrorCode(StrEnum):
    UNAVAILABLE = "gemini_unavailable"
    DEADLINE_EXCEEDED = "gemini_deadline_exceeded"
    OUTPUT_TRUNCATED = "gemini_output_truncated"
    NO_CANDIDATE = "gemini_no_candidate"
    MALFORMED_JSON = "gemini_malformed_json"


class GeminiError(RuntimeError):
    def __init__(self, code: GeminiErrorCode, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code



@dataclass
class CircuitBreaker:
    """Skip a model for `cooldown` seconds after `threshold` consecutive failures.

    No lock: the agent runs on one event loop and nothing awaits between a check and its update.
    """

    threshold: int = BREAKER_THRESHOLD
    cooldown: float = BREAKER_COOLDOWN_SECONDS
    clock: Callable[[], float] = time.monotonic
    failures: int = field(default=0, init=False)
    opened_at: float | None = field(default=None, init=False)

    def is_open(self) -> bool:
        return self.opened_at is not None and self.clock() - self.opened_at < self.cooldown

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened_at = self.clock()


_breakers: dict[str, CircuitBreaker] = {}
_deadline: ContextVar[float | None] = ContextVar("gemini_deadline", default=None)


@contextmanager
def deadline(seconds: float | None = None) -> Iterator[None]:
    """Every Gemini call inside this block shares one time budget."""
    budget = seconds if seconds is not None else _configured_deadline()
    token = _deadline.set(time.monotonic() + budget)
    try:
        yield
    finally:
        _deadline.reset(token)


def _configured_deadline() -> float:
    raw = os.getenv("AGENT_DEADLINE_SECONDS", "")
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_DEADLINE_SECONDS
    return value if value > 0 else DEFAULT_DEADLINE_SECONDS


def remaining_seconds() -> float:
    end = _deadline.get()
    return math.inf if end is None else end - time.monotonic()


def models_in_order() -> list[str]:
    """Primary first, then the fallback when one is configured and differs."""
    primary = os.getenv("GEMINI_AGENT_MODEL") or DEFAULT_MODEL
    fallback = os.getenv("GEMINI_FALLBACK_MODEL") or ""
    return [primary, fallback] if fallback and fallback != primary else [primary]


def breaker_for(model: str) -> CircuitBreaker:
    return _breakers.setdefault(model, CircuitBreaker())


def gemini_payload(prompt: str, response_schema: dict | None = None,
                   max_output_tokens: int | None = None) -> dict:
    config: dict = {"temperature": TEMPERATURE}
    if max_output_tokens is not None:
        config["maxOutputTokens"] = max_output_tokens
    if response_schema is not None:
        config |= {"responseMimeType": "application/json", "responseSchema": response_schema}
    return {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": config}


def reply_text(body: dict) -> str:
    """The text of a reply, refusing a cut-off one: a truncated draft must not pass as whole."""
    candidates = body.get("candidates") or []
    if not candidates:
        raise GeminiError(GeminiErrorCode.NO_CANDIDATE, "no candidate (blocked or empty)")
    if candidates[0].get("finishReason") == FINISH_TRUNCATED:
        raise GeminiError(GeminiErrorCode.OUTPUT_TRUNCATED, "reply hit maxOutputTokens")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    return "".join(part.get("text", "") for part in parts).strip()


def parse_reply(body: dict, is_json: bool) -> dict | str:
    text = reply_text(body)
    if not is_json:
        return text
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise GeminiError(GeminiErrorCode.MALFORMED_JSON, str(error)) from error


def backoff_seconds(attempt: int, retry_after: str | None) -> float:
    """Full-jitter exponential backoff, or the server's Retry-After when it gives seconds."""
    if retry_after and retry_after.isdigit():
        return float(retry_after)
    return random.uniform(0, min(BACKOFF_CAP_SECONDS, BACKOFF_BASE_SECONDS * 2 ** attempt))


async def _post(model: str, payload: dict, timeout: float) -> httpx.Response:
    base_url = (os.getenv("GEMINI_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    headers = {"Content-Type": "application/json",
               "X-goog-api-key": os.getenv("GOOGLE_API_KEY", "")}
    async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
        return await client.post(f"{base_url}/models/{model}:generateContent",
                                 headers=headers, json=payload)


def _attempt_timeout() -> float:
    left = remaining_seconds()
    if left <= 0:
        raise GeminiError(GeminiErrorCode.DEADLINE_EXCEEDED, "draft deadline spent")
    return min(ATTEMPT_TIMEOUT_SECONDS, left)


async def _wait_before_retry(model: str, attempt: int, retry_after: str | None) -> None:
    delay = backoff_seconds(attempt, retry_after)
    if delay >= remaining_seconds():
        raise GeminiError(GeminiErrorCode.DEADLINE_EXCEEDED, f"no time left to retry {model}")
    await asyncio.sleep(delay)


async def call_model(model: str, payload: dict) -> dict:
    """One model, retried on transient failures within the shared deadline."""
    for attempt in range(ATTEMPTS_PER_MODEL):
        try:
            response = await _post(model, payload, _attempt_timeout())
        except httpx.TransportError as error:
            logger.warning("gemini %s attempt %d failed: %r", model, attempt + 1, error)
            retry_after = None
        else:
            if response.is_success:
                return response.json()
            if response.status_code not in RETRYABLE_STATUS:
                raise GeminiError(GeminiErrorCode.UNAVAILABLE,
                                  f"{model} returned {response.status_code}")
            logger.warning("gemini %s attempt %d returned %d", model, attempt + 1,
                           response.status_code)
            retry_after = response.headers.get("retry-after")
        if attempt + 1 < ATTEMPTS_PER_MODEL:
            await _wait_before_retry(model, attempt, retry_after)
    raise GeminiError(GeminiErrorCode.UNAVAILABLE, f"{model}: {ATTEMPTS_PER_MODEL} attempts failed")


async def generate(prompt: str, response_schema: dict | None = None,
                   max_output_tokens: int | None = None) -> dict | str:
    """Ask the primary model, then the fallback; parsed JSON when a schema is given."""
    payload = gemini_payload(prompt, response_schema, max_output_tokens)
    models = models_in_order()
    failure: GeminiError | None = None
    for position, model in enumerate(models):
        breaker = breaker_for(model)
        # The last model is always tried: skipping it would leave nothing to answer.
        if breaker.is_open() and position < len(models) - 1:
            logger.warning("gemini %s skipped: circuit open", model)
            continue
        try:
            body = await call_model(model, payload)
        except GeminiError as error:
            if error.code == GeminiErrorCode.DEADLINE_EXCEEDED:
                raise
            breaker.record_failure()
            failure = error
            logger.warning("gemini %s failed, trying the next model: %s", model, error)
            continue
        breaker.record_success()
        return parse_reply(body, is_json=response_schema is not None)
    raise failure or GeminiError(GeminiErrorCode.UNAVAILABLE, "no model configured")
