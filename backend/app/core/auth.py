"""Bearer-token authentication for the backend API.

Closes the audit's OWASP API1 finding: before this, anyone who could reach :8000 could call
POST /emails/{id}/send and dispatch a real Gmail reply.

The check is deliberately a single shared token rather than per-user JWTs — AImail serves one
shared mailbox, so per-user identity buys nothing today. Swapping in Supabase JWT verification
later means rewriting only this file: every route already depends on `require_auth`.

Applied app-wide (see main.py) rather than per route, so a route added later is protected by
default; exempting a path is then a deliberate edit to _EXEMPT_PATHS.
"""

import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings

# The demo page is the one unauthenticated surface: it doubles as the liveness check.
_EXEMPT_PATHS = frozenset({"/"})

_bearer = HTTPBearer(auto_error=False)


async def require_auth(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> None:
    if request.url.path in _EXEMPT_PATHS:
        return

    expected = get_settings().backend_api_token
    if not expected:
        # Fail closed: an unset token must not silently disable auth.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="BACKEND_API_TOKEN is not configured; the API is refusing all requests.",
        )

    if credentials is None or not secrets.compare_digest(credentials.credentials, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
