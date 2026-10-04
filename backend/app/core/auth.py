"""Who is calling the API, and whose mail they may see (docs/adr/0005).

Three ways in, checked in order: the shared BACKEND_API_TOKEN as a bearer (scripts and tests only,
never shipped to a browser); a Supabase access token as a bearer (the extension and Outlook add-in);
the dashboard's HttpOnly session cookie. Applied app-wide (see main.py), so a route added later is
protected by default; exempting a path is a deliberate edit below.
"""

import logging
import secrets
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core import ownership, supabase_auth
from app.core.config import get_settings
from app.core.ownership import Scope

SESSION_COOKIE = "aimail_session"
CLIENT_HEADER = "X-AIMail-Client"

# The demo page doubles as the liveness check; the sign-in routes run before there is a session.
_EXEMPT_PATHS = frozenset({"/"})
_EXEMPT_PREFIXES = ("/auth/",)
_STATE_CHANGING = frozenset({"POST", "PUT", "PATCH", "DELETE"})

_bearer = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


class AuthError(StrEnum):
    SIGNED_OUT = "signed_out"
    SESSION_INVALID = "session_invalid"
    CLIENT_HEADER_MISSING = "client_header_missing"
    SUPABASE_UNAVAILABLE = "supabase_unavailable"


def _fail(status_code: int, code: AuthError) -> HTTPException:
    headers = {"WWW-Authenticate": "Bearer"} if status_code == status.HTTP_401_UNAUTHORIZED else None
    return HTTPException(status_code=status_code, detail=code, headers=headers)


@dataclass(frozen=True)
class Principal:
    """The caller. A script holding the shared token is not a person and has no email."""

    email: str
    user_id: UUID | None = None
    is_service: bool = False


SERVICE = Principal(email="", is_service=True)


async def scope_of_principal(principal: Principal) -> Scope | None:
    """Whose rows the caller may touch, or None when no mailbox is connected for them."""
    if principal.is_service:
        return ownership.EVERYTHING
    return await ownership.scope_for(principal.user_id, principal.email)


def _user_id(claims: dict) -> UUID | None:
    try:
        return UUID(claims.get("sub", ""))
    except ValueError:
        return None


async def _user(token: str) -> Principal:
    try:
        claims = await supabase_auth.verify_access_token(token)
    except supabase_auth.SupabaseNotConfiguredError as exc:
        # Without Supabase no session can be valid, so this credential is invalid, not an outage.
        logger.warning("a session was presented but Supabase sign-in is not configured: %s", exc)
        raise _fail(status.HTTP_401_UNAUTHORIZED, AuthError.SESSION_INVALID) from exc
    except supabase_auth.SupabaseUnavailableError as exc:
        raise _fail(status.HTTP_503_SERVICE_UNAVAILABLE, AuthError.SUPABASE_UNAVAILABLE) from exc
    except supabase_auth.InvalidTokenError as exc:
        raise _fail(status.HTTP_401_UNAUTHORIZED, AuthError.SESSION_INVALID) from exc
    return Principal(email=claims.get("email", ""), user_id=_user_id(claims))


async def current_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal:
    """The caller behind the request, or 401. Raises 403 for a cookie write without the header."""
    if credentials is not None:
        expected = get_settings().backend_api_token
        # An unset token never matches, so it cannot switch authentication off.
        if expected and secrets.compare_digest(credentials.credentials, expected):
            return SERVICE
        return await _user(credentials.credentials)
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise _fail(status.HTTP_401_UNAUTHORIZED, AuthError.SIGNED_OUT)
    # A form cannot send a custom header, and another origin's script cannot without a preflight,
    # which only the dashboard origins pass (app/core/cors.py). SameSite alone is not enough.
    if request.method in _STATE_CHANGING and request.headers.get(CLIENT_HEADER) != "1":
        raise _fail(status.HTTP_403_FORBIDDEN, AuthError.CLIENT_HEADER_MISSING)
    return await _user(token)


async def require_auth(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> None:
    path = request.url.path
    if path in _EXEMPT_PATHS or path.startswith(_EXEMPT_PREFIXES):
        return
    request.state.principal = await current_principal(request, credentials)


def principal_of(request: Request) -> Principal:
    """The principal require_auth attached; routes read it instead of re-checking."""
    return request.state.principal


async def require_mailbox(request: Request) -> None:
    """404 rather than 403 for someone else's mail, so an id reveals nothing about what exists."""
    scope = await scope_of_principal(principal_of(request))
    if scope is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    request.state.scope = scope


def scope_of(request: Request) -> Scope:
    """The scope require_mailbox attached; only valid on routes that depend on it."""
    return request.state.scope
