"""Gemini calls for the Lane C agent: one deadline per draft, retries, a fallback model, a breaker.

Every stage of a draft (route, summarise, draft, critique, refine) shares one deadline, so a draft
that cannot finish fails here with a reason instead of at the dashboard's HTTP timeout with none.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx

from app.core.config import get_settings
from model_runtime import (
    OUTCOME_CIRCUIT_OPEN,
    OUTCOME_OK,
    OUTCOME_TRANSPORT_ERROR,
    ModelError,
    ModelErrorCode,
    record_call,
    remaining_seconds,
)

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-3.5-flash-lite"
# Greedy decoding for reproducibility. Reduces sampling randomness; does not guarantee determinism.
TEMPERATURE = 0.0
ATTEMPT_TIMEOUT_SECONDS = 30.0
ATTEMPTS_PER_MODEL = 3
BACKOFF_BASE_SECONDS = 2.0
BACKOFF_CAP_SECONDS = 10.0
RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})
BREAKER_THRESHOLD = 3
BREAKER_COOLDOWN_SECONDS = 60.0
FINISH_TRUNCATED = "MAX_TOKENS"

# Tests swap this for httpx.MockTransport; production leaves it None.
transport: httpx.AsyncBaseTransport | None = None


# Payload too large: always the input's fault.
PAYLOAD_TOO_LARGE = 413
INVALID_ARGUMENT = "INVALID_ARGUMENT"
# Gemini also answers 400 INVALID_ARGUMENT for a bad key; that is configuration, not the input.
API_KEY_REASONS = frozenset({"API_KEY_INVALID", "API_KEY_EXPIRED"})


def is_input_rejected(response: httpx.Response) -> bool:
    """The request itself was at fault, so no retry and no other model would help.

    Only a 413, or a 400 INVALID_ARGUMENT that is not about the API key. A bad key, an expired
    one, an unsupported location (400 FAILED_PRECONDITION) or a 403 is configuration: it must stay
    retryable later, or a config slip would mark every pending message undraftable.
    """
    if response.status_code == PAYLOAD_TOO_LARGE:
        return True
    if response.status_code != 400:
        return False
    try:
        error = response.json().get("error") or {}
    except ValueError:
        return False
    reasons = {detail.get("reason") for detail in error.get("details") or [] if isinstance(detail, dict)}
    return error.get("status") == INVALID_ARGUMENT and not reasons & API_KEY_REASONS
FINISH_STOP = "STOP"


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


def models_in_order() -> list[str]:
    """Primary first, then the fallback when one is configured and differs."""
    primary = get_settings().gemini_agent_model or DEFAULT_MODEL
    fallback = get_settings().gemini_fallback_model
    return [primary, fallback] if fallback and fallback != primary else [primary]


def breaker_for(model: str) -> CircuitBreaker:
    return _breakers.setdefault(model, CircuitBreaker())


def gemini_payload(prompt: str, response_schema: dict | None = None,
                   max_output_tokens: int | None = None, system: str | None = None) -> dict:
    config: dict = {"temperature": TEMPERATURE}
    if max_output_tokens is not None:
        config["maxOutputTokens"] = max_output_tokens
    if response_schema is not None:
        config |= {"responseMimeType": "application/json", "responseSchema": response_schema}
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": config}
    # The rules travel apart from the fenced email text, so the text cannot pose as them.
    return payload | {"systemInstruction": {"parts": [{"text": system}]}} if system else payload


def reply_text(body: dict) -> str:
    """The text of a complete reply. Cut off, blocked (SAFETY, RECITATION ...) or empty all raise:
    none of them may pass as a draft or a summary."""
    candidates = body.get("candidates") or []
    if not candidates:
        raise ModelError(ModelErrorCode.NO_CANDIDATE, "no candidate (blocked or empty)")
    finish = candidates[0].get("finishReason", FINISH_STOP)
    if finish == FINISH_TRUNCATED:
        raise ModelError(ModelErrorCode.OUTPUT_TRUNCATED, "reply hit maxOutputTokens")
    if finish != FINISH_STOP:
        raise ModelError(ModelErrorCode.NO_CANDIDATE, f"reply stopped: {finish}")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(part.get("text", "") for part in parts).strip()
    if not text:
        raise ModelError(ModelErrorCode.NO_CANDIDATE, "empty reply")
    return text


def parse_reply(body: dict, is_json: bool) -> dict | str:
    text = reply_text(body)
    if not is_json:
        return text
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise ModelError(ModelErrorCode.MALFORMED_JSON, str(error)) from error


def backoff_seconds(attempt: int, retry_after: str | None) -> float:
    """Full-jitter exponential backoff, or the server's Retry-After when it gives seconds."""
    if retry_after and retry_after.isdigit():
        return float(retry_after)
    return random.uniform(0, min(BACKOFF_CAP_SECONDS, BACKOFF_BASE_SECONDS * 2 ** attempt))


class _GiveUpOnModel(Exception):
    """Waiting for this model is pointless within the budget; the next model may answer now."""


async def _post(model: str, payload: dict, timeout: float) -> httpx.Response:
    base_url = (get_settings().gemini_base_url or DEFAULT_BASE_URL).rstrip("/")
    headers = {"Content-Type": "application/json",
               "X-goog-api-key": get_settings().google_api_key}
    # httpx's timeout bounds each phase (connect, write, read) separately; asyncio.timeout bounds
    # the whole attempt, so one slow call cannot run past the shared deadline.
    async with asyncio.timeout(timeout), httpx.AsyncClient(timeout=timeout, transport=transport) as client:
        return await client.post(f"{base_url}/models/{model}:generateContent",
                                 headers=headers, json=payload)


def _attempt_timeout() -> float:
    left = remaining_seconds()
    if left <= 0:
        raise ModelError(ModelErrorCode.DEADLINE_EXCEEDED, "draft deadline spent")
    return min(ATTEMPT_TIMEOUT_SECONDS, left)


async def _wait_before_retry(model: str, attempt: int, retry_after: str | None) -> None:
    """Sleep before the next try on this model, or give up on it so the fallback can answer.

    A Retry-After longer than the backoff cap, or longer than the budget left, is a reason to move
    on, not to spend the draft's deadline waiting on one provider.
    """
    delay = backoff_seconds(attempt, retry_after)
    if delay > BACKOFF_CAP_SECONDS or delay >= remaining_seconds():
        raise _GiveUpOnModel(f"{model}: waiting {delay:.0f}s is not worth the budget")
    await asyncio.sleep(delay)


async def call_model(model: str, payload: dict) -> dict:
    """One model, retried on transient failures within the shared deadline."""
    for attempt in range(ATTEMPTS_PER_MODEL):
        started = time.monotonic()
        try:
            response = await _post(model, payload, _attempt_timeout())
        except (httpx.TransportError, TimeoutError) as error:
            record_call(model, OUTCOME_TRANSPORT_ERROR, started)
            logger.warning("gemini %s attempt %d failed: %r", model, attempt + 1, error)
            retry_after = None
        else:
            record_call(model, OUTCOME_OK if response.is_success else f"http_{response.status_code}",
                    started)
            if response.is_success:
                return response.json()
            if is_input_rejected(response):
                raise ModelError(ModelErrorCode.REJECTED,
                                  f"{model} rejected the request: {response.status_code}")
            if response.status_code not in RETRYABLE_STATUS:
                raise ModelError(ModelErrorCode.UNAVAILABLE,
                                  f"{model} returned {response.status_code}")
            logger.warning("gemini %s attempt %d returned %d", model, attempt + 1,
                           response.status_code)
            retry_after = response.headers.get("retry-after")
        if attempt + 1 < ATTEMPTS_PER_MODEL:
            try:
                await _wait_before_retry(model, attempt, retry_after)
            except _GiveUpOnModel as give_up:
                raise ModelError(ModelErrorCode.UNAVAILABLE, str(give_up)) from give_up
    raise ModelError(ModelErrorCode.UNAVAILABLE, f"{model}: {ATTEMPTS_PER_MODEL} attempts failed")


async def generate(prompt: str, response_schema: dict | None = None,
                   max_output_tokens: int | None = None, system: str | None = None) -> dict | str:
    """Ask the primary model, then the fallback; parsed JSON when a schema is given."""
    payload = gemini_payload(prompt, response_schema, max_output_tokens, system)
    models = models_in_order()
    failure: ModelError | None = None
    for position, model in enumerate(models):
        breaker = breaker_for(model)
        # The last model is always tried: skipping it would leave nothing to answer.
        if breaker.is_open() and position < len(models) - 1:
            record_call(model, OUTCOME_CIRCUIT_OPEN, time.monotonic())
            logger.warning("gemini %s skipped: circuit open", model)
            continue
        try:
            body = await call_model(model, payload)
        except ModelError as error:
            # Out of time, or the request itself is at fault: no other model would do better, and
            # a bad input must not open the breaker for every other user.
            if error.code in (ModelErrorCode.DEADLINE_EXCEEDED, ModelErrorCode.REJECTED):
                raise
            breaker.record_failure()
            failure = error
            logger.warning("gemini %s failed, trying the next model: %s", model, error)
            continue
        breaker.record_success()
        return parse_reply(body, is_json=response_schema is not None)
    raise failure or ModelError(ModelErrorCode.UNAVAILABLE, "no model configured")
