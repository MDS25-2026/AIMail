"""The backend's client for the agent (:8001): one connection pool, typed requests, validated answers.

A new HTTP client per call wasted a connection each time, and answers were read as loose dicts. Requests
are the shared models (app/agent_contract.py), and every answer is validated against its model, so a
contract change on one side fails loudly. A connection refused (the agent restarting) is tried once more;
anything else is not retried here, since the agent has its own retries and deadline.
"""

import asyncio
from typing import TypeVar

import httpx
from pydantic import BaseModel

from app.core.agent_auth import agent_headers
from app.core.config import get_settings
from app.core.logging_setup import request_id
from app.core.middleware import REQUEST_ID_HEADER

# Lane C runs a multi-step pipeline under its own 100 s deadline; this sits just above it.
AGENT_TIMEOUT_SECONDS = 120
CONNECT_RETRY_DELAY_SECONDS = 1.0

Answer = TypeVar("Answer", bound=BaseModel)

_client: httpx.AsyncClient | None = None


def _shared_client() -> httpx.AsyncClient:
    global _client  # one pool for the process, created on first use
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=AGENT_TIMEOUT_SECONDS)
    return _client


async def close() -> None:
    if _client is not None:
        await _client.aclose()


async def _post(path: str, request: BaseModel) -> httpx.Response:
    url = get_settings().email_agent_url.rstrip("/") + path
    headers = {REQUEST_ID_HEADER: request_id.get(), **agent_headers()}
    try:
        return await _shared_client().post(url, json=request.model_dump(mode="json"), headers=headers)
    except httpx.ConnectError:
        await asyncio.sleep(CONNECT_RETRY_DELAY_SECONDS)
        return await _shared_client().post(url, json=request.model_dump(mode="json"), headers=headers)


async def call(path: str, request: BaseModel, answer: type[Answer]) -> Answer:
    """Raises httpx.HTTPStatusError for an agent refusal, pydantic.ValidationError for a malformed answer."""
    response = await _post(path, request)
    response.raise_for_status()
    return answer.model_validate(response.json())
