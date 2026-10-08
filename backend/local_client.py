"""The local model (Private mode, specs/features/local-model.md): Ollama on the company's own machine.

Same contract as gemini_client.generate, so email_agent switches between them in one place. A
failure raises GeminiError with the same codes, so the agent answers it the same way; it never
falls back to Gemini, which would override the user's choice to keep their email in the company.
"""

import json
import math

import httpx

from app.core.config import get_settings
from gemini_client import GeminiError, GeminiErrorCode, remaining_seconds

DEFAULT_URL = "http://localhost:11434"
CHAT_PATH = "/api/chat"
TEMPERATURE = 0
# The local model writes shorter replies than its window allows; a cap keeps a runaway answer short.
MAX_OUTPUT_TOKENS = 1024


def configured_model() -> str:
    """The company's local model; "" means Private mode is not set up here."""
    return get_settings().local_llm_model.strip()


def _payload(model: str, prompt: str, response_schema: dict | None, max_output_tokens: int | None) -> dict:
    limit = min(max_output_tokens or MAX_OUTPUT_TOKENS, MAX_OUTPUT_TOKENS)
    payload = {
        "model": model, "stream": False, "think": False,
        "options": {"temperature": TEMPERATURE, "num_predict": limit},
        "messages": [{"role": "user", "content": prompt}],
    }
    if response_schema is not None:
        payload["format"] = response_schema
    return payload


async def generate_local(prompt: str, response_schema: dict | None = None,
                         max_output_tokens: int | None = None) -> dict | str:
    """Parsed JSON when a schema is given, as gemini_client.generate returns."""
    model = configured_model()
    if not model:
        raise GeminiError(GeminiErrorCode.UNAVAILABLE, "private mode is not configured (LOCAL_LLM_MODEL)")
    url = (get_settings().local_llm_url or DEFAULT_URL).rstrip("/") + CHAT_PATH
    budget = remaining_seconds()
    if budget <= 0:
        raise GeminiError(GeminiErrorCode.DEADLINE_EXCEEDED, "draft deadline spent")
    try:
        # Outside a request's deadline the budget is infinite, which httpx spells None.
        async with httpx.AsyncClient(timeout=None if math.isinf(budget) else budget) as client:
            response = await client.post(url, json=_payload(model, prompt, response_schema, max_output_tokens))
            response.raise_for_status()
        text = response.json()["message"]["content"]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise GeminiError(GeminiErrorCode.UNAVAILABLE, f"local model {model}: {exc}") from exc
    if response_schema is None:
        return text.strip()
    try:
        return json.loads(text)
    except ValueError as exc:
        raise GeminiError(GeminiErrorCode.MALFORMED_JSON, f"local model {model}: not JSON") from exc
