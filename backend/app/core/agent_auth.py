"""Service-to-service authentication for the agent (:8001), which relays text to the model.

The backend sends AGENT_TOKEN in a header and the agent checks it. With no token configured (dev), the
agent answers loopback callers only; a deployed environment cannot start without one (app/core/config.py).
"""

import hmac

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from app.core.config import LOCAL_HOSTS, get_settings
from app.core.errors import ErrorCode, error_response

AGENT_TOKEN_HEADER = "X-AIMail-Agent-Token"


def agent_headers() -> dict[str, str]:
    token = get_settings().agent_token
    return {AGENT_TOKEN_HEADER: token} if token else {}


def _is_allowed(request: Request) -> bool:
    token = get_settings().agent_token
    if token:
        return hmac.compare_digest(request.headers.get(AGENT_TOKEN_HEADER, ""), token)
    return request.client is not None and request.client.host in LOCAL_HOSTS


async def require_agent_token(request: Request, call_next: RequestResponseEndpoint) -> Response | JSONResponse:
    if not _is_allowed(request):
        return error_response(ErrorCode.FORBIDDEN, "agent token missing or wrong")
    return await call_next(request)
