"""The local model (Private mode, specs/features/local-model.md): Ollama on the company's own machine.

The same contract as gemini_client.generate: a cut-off reply raises OUTPUT_TRUNCATED rather than passing
as whole, every attempt is recorded, and failures are ModelErrors. It never falls back to Gemini, which
would override the user's choice to keep their email in the company. Callers go through model_gateway.
"""

import json
import math
import time

import httpx

from app.core.config import get_settings
from model_runtime import ModelError, ModelErrorCode, record_call, remaining_seconds

DEFAULT_URL = "http://localhost:11434"
CHAT_PATH = "/api/chat"
TEMPERATURE = 0
PROVIDER = "local"
# Used only when the caller sets no budget; each stage passes its own, as it does for Gemini.
DEFAULT_MAX_OUTPUT_TOKENS = 2048
# Ollama's done_reason when the reply hit num_predict.
DONE_TRUNCATED = "length"

# Tests swap this for httpx.MockTransport; production leaves it None.
transport: httpx.AsyncBaseTransport | None = None


def configured_model() -> str:
    """The company's local model; "" means Private mode is not set up here."""
    return get_settings().local_llm_model.strip()


def _payload(model: str, prompt: str, system: str | None, response_schema: dict | None,
             max_output_tokens: int | None) -> dict:
    messages = [{"role": "system", "content": system}] if system else []
    payload = {
        "model": model, "stream": False, "think": False,
        "options": {"temperature": TEMPERATURE, "num_predict": max_output_tokens or DEFAULT_MAX_OUTPUT_TOKENS},
        "messages": [*messages, {"role": "user", "content": prompt}],
    }
    if response_schema is not None:
        payload["format"] = response_schema
    return payload


def _budget() -> float | None:
    left = remaining_seconds()
    if left <= 0:
        raise ModelError(ModelErrorCode.DEADLINE_EXCEEDED, "draft deadline spent")
    # Outside a request's deadline the budget is infinite, which httpx spells None.
    return None if math.isinf(left) else left


async def _post(model: str, payload: dict) -> dict:
    url = (get_settings().local_llm_url or DEFAULT_URL).rstrip("/") + CHAT_PATH
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=_budget(), transport=transport) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            body = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        record_call(model, "transport_error", started, PROVIDER)
        raise ModelError(ModelErrorCode.UNAVAILABLE, f"local model {model}: {exc}") from exc
    record_call(model, "truncated" if body.get("done_reason") == DONE_TRUNCATED else "ok", started, PROVIDER)
    return body


def _reply_text(model: str, body: dict) -> str:
    """The text of a complete reply; cut off or empty raise, as Gemini's do."""
    if body.get("done_reason") == DONE_TRUNCATED:
        raise ModelError(ModelErrorCode.OUTPUT_TRUNCATED, f"local model {model} hit its output budget")
    text = ((body.get("message") or {}).get("content") or "").strip()
    if not text:
        raise ModelError(ModelErrorCode.NO_CANDIDATE, f"local model {model} returned nothing")
    return text


async def generate_local(prompt: str, response_schema: dict | None = None, max_output_tokens: int | None = None,
                         system: str | None = None) -> dict | str:
    """Parsed JSON when a schema is given, as gemini_client.generate returns."""
    model = configured_model()
    if not model:
        raise ModelError(ModelErrorCode.UNAVAILABLE, "private mode is not configured (LOCAL_LLM_MODEL)")
    text = _reply_text(model, await _post(model, _payload(model, prompt, system, response_schema,
                                                          max_output_tokens)))
    if response_schema is None:
        return text
    try:
        return json.loads(text)
    except ValueError as exc:
        raise ModelError(ModelErrorCode.MALFORMED_JSON, f"local model {model}: not JSON") from exc
