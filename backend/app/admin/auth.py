"""Supabase Auth for the admin console (docs/adr/0004).

The browser never holds a token. The backend exchanges credentials with Supabase and keeps the
session in HttpOnly cookies; every admin request verifies the access token locally against the
project's published ES256 keys (app/core/supabase_auth.py) and requires app_metadata.role == "admin".
"""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Cookie, Header, HTTPException, Response, status

from app.core import supabase_auth
from app.core.config import get_settings
from app.core.errors import ErrorCode
from app.core.supabase_auth import Session

ACCESS_COOKIE = "aimail_admin"
REFRESH_COOKIE = "aimail_admin_refresh"
ACCESS_COOKIE_PATH = "/admin"
REFRESH_COOKIE_PATH = "/admin/session"
REFRESH_MAX_AGE_SECONDS = 7 * 24 * 60 * 60
CSRF_HEADER = "X-AIMail-Admin"
ADMIN_ROLE = "admin"



def _fail(status_code: int, code: ErrorCode) -> HTTPException:
    return HTTPException(status_code=status_code, detail=code)


def _from_supabase(exc: Exception, grant_failure: ErrorCode) -> HTTPException:
    """The admin console's HTTP answer for a shared-plumbing failure."""
    if isinstance(exc, supabase_auth.SupabaseNotConfiguredError):
        return _fail(status.HTTP_503_SERVICE_UNAVAILABLE, ErrorCode.ADMIN_AUTH_NOT_CONFIGURED)
    if isinstance(exc, supabase_auth.SupabaseUnavailableError):
        return _fail(status.HTTP_503_SERVICE_UNAVAILABLE, ErrorCode.SUPABASE_UNAVAILABLE)
    return _fail(status.HTTP_401_UNAUTHORIZED, grant_failure)


_SUPABASE_FAILURES = (supabase_auth.SupabaseNotConfiguredError, supabase_auth.SupabaseUnavailableError,
                      supabase_auth.InvalidTokenError, supabase_auth.InvalidGrantError)


@dataclass(frozen=True)
class Admin:
    user_id: str
    email: str


async def verify_admin(token: str) -> Admin:
    """The admin behind a valid access token. 401 for a bad token, 403 for a non-admin."""
    try:
        claims = await supabase_auth.verify_access_token(token)
    except _SUPABASE_FAILURES as exc:
        raise _from_supabase(exc, ErrorCode.ADMIN_SESSION_INVALID) from exc
    if (claims.get("app_metadata") or {}).get("role") != ADMIN_ROLE:
        raise _fail(status.HTTP_403_FORBIDDEN, ErrorCode.NOT_AN_ADMIN)
    return Admin(user_id=claims["sub"], email=claims.get("email", ""))


async def require_admin(
    token: Annotated[str | None, Cookie(alias=ACCESS_COOKIE)] = None,
) -> Admin:
    if not token:
        raise _fail(status.HTTP_401_UNAUTHORIZED, ErrorCode.ADMIN_SIGNED_OUT)
    return await verify_admin(token)


async def require_admin_header(
    marker: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> None:
    """A state-changing admin call must carry a custom header: a form cannot send one, and a
    cross-origin script cannot without a preflight, which only ADMIN_ORIGINS pass (app/core/cors.py).
    SameSite alone is not enough: every localhost port is the same site."""
    if marker != "1":
        raise _fail(status.HTTP_403_FORBIDDEN, ErrorCode.ADMIN_HEADER_MISSING)


async def sign_in(email: str, password: str) -> Session:
    try:
        return await supabase_auth.password_session(email, password)
    except _SUPABASE_FAILURES as exc:
        raise _from_supabase(exc, ErrorCode.INVALID_CREDENTIALS) from exc


async def refresh(refresh_token: str) -> Session:
    try:
        return await supabase_auth.refresh_session(refresh_token)
    except _SUPABASE_FAILURES as exc:
        raise _from_supabase(exc, ErrorCode.ADMIN_SIGNED_OUT) from exc


async def sign_out(access_token: str) -> None:
    """Revoke the session at Supabase. Best effort: the cookies are cleared either way."""
    await supabase_auth.revoke(access_token)


def set_session_cookies(response: Response, session: Session) -> None:
    secure = get_settings().admin_cookie_secure
    response.set_cookie(ACCESS_COOKIE, session.access_token, max_age=session.expires_in,
                        path=ACCESS_COOKIE_PATH, httponly=True, secure=secure, samesite="strict")
    response.set_cookie(REFRESH_COOKIE, session.refresh_token, max_age=REFRESH_MAX_AGE_SECONDS,
                        path=REFRESH_COOKIE_PATH, httponly=True, secure=secure, samesite="strict")


def clear_session_cookies(response: Response) -> None:
    secure = get_settings().admin_cookie_secure
    response.delete_cookie(ACCESS_COOKIE, path=ACCESS_COOKIE_PATH, httponly=True, secure=secure,
                           samesite="strict")
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH, httponly=True, secure=secure,
                           samesite="strict")
