"""Supabase Auth for the admin console (docs/adr/0004).

The browser never holds a token. The backend exchanges credentials with Supabase and keeps the
session in HttpOnly cookies; every admin request verifies the access token locally against the
project's published ES256 keys and requires app_metadata.role == "admin".
"""

import asyncio
import math
import time
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from typing import Annotated

import httpx
import jwt
from fastapi import Cookie, Header, HTTPException, Response, status

from app.core.config import get_settings

ACCESS_COOKIE = "aimail_admin"
REFRESH_COOKIE = "aimail_admin_refresh"
ACCESS_COOKIE_PATH = "/admin"
REFRESH_COOKIE_PATH = "/admin/session"
REFRESH_MAX_AGE_SECONDS = 7 * 24 * 60 * 60
CSRF_HEADER = "X-AIMail-Admin"
ADMIN_ROLE = "admin"
AUDIENCE = "authenticated"
ALGORITHMS = ["ES256"]
JWKS_CACHE_SECONDS = 600
JWKS_REFETCH_SECONDS = 60
SUPABASE_TIMEOUT_SECONDS = 10.0

# Tests swap this for httpx.MockTransport.
transport: httpx.AsyncBaseTransport | None = None


class AdminAuthError(StrEnum):
    NOT_CONFIGURED = "admin_auth_not_configured"
    SIGNED_OUT = "admin_signed_out"
    SESSION_INVALID = "admin_session_invalid"
    NOT_ADMIN = "not_an_admin"
    BAD_CREDENTIALS = "invalid_credentials"
    CSRF_HEADER_MISSING = "admin_header_missing"
    SUPABASE_UNAVAILABLE = "supabase_unavailable"


def _fail(status_code: int, code: AdminAuthError) -> HTTPException:
    return HTTPException(status_code=status_code, detail=code)


@dataclass(frozen=True)
class Admin:
    user_id: str
    email: str


@dataclass(frozen=True)
class Session:
    access_token: str
    refresh_token: str
    expires_in: int


def _auth_base() -> str:
    settings = get_settings()
    if not (settings.supabase_url and settings.supabase_anon_key):
        raise _fail(status.HTTP_503_SERVICE_UNAVAILABLE, AdminAuthError.NOT_CONFIGURED)
    return settings.supabase_url.rstrip("/") + "/auth/v1"


class _KeySet:
    """The project's signing keys by key id, refetched on an unknown id at most once a minute.

    PyJWKClient refetches on every unknown kid, so a stream of forged cookies would each cost a
    blocking fetch to Supabase. A real key rotation still lands within JWKS_REFETCH_SECONDS.
    """

    def __init__(self, auth_base: str) -> None:
        self._client = jwt.PyJWKClient(f"{auth_base}/.well-known/jwks.json", cache_keys=False)
        self._keys: dict[str, object] = {}
        self._fetched_at = -math.inf

    def _refresh(self) -> None:
        self._keys = {key.key_id: key.key for key in self._client.get_signing_keys()}
        self._fetched_at = time.monotonic()

    def get_signing_key_from_jwt(self, token: str) -> "_Key":
        kid = jwt.get_unverified_header(token).get("kid")
        is_stale = time.monotonic() - self._fetched_at >= JWKS_CACHE_SECONDS
        may_refetch = time.monotonic() - self._fetched_at >= JWKS_REFETCH_SECONDS
        if is_stale or (kid not in self._keys and may_refetch):
            self._refresh()
        if kid not in self._keys:
            raise jwt.InvalidTokenError("unknown signing key")
        return _Key(self._keys[kid])


@dataclass(frozen=True)
class _Key:
    key: object


@lru_cache(maxsize=1)
def _jwks(auth_base: str) -> _KeySet:
    return _KeySet(auth_base)


def _decode(token: str, auth_base: str) -> dict:
    key = _jwks(auth_base).get_signing_key_from_jwt(token).key
    return jwt.decode(token, key, algorithms=ALGORITHMS, audience=AUDIENCE, issuer=auth_base,
                      options={"require": ["exp", "sub", "aud", "iss"]})


async def verify_admin(token: str) -> Admin:
    """The admin behind a valid access token. 401 for a bad token, 403 for a non-admin."""
    auth_base = _auth_base()
    try:
        # The JWKS fetch is blocking the first time and every JWKS_CACHE_SECONDS after.
        claims = await asyncio.to_thread(_decode, token, auth_base)
    except jwt.PyJWKClientConnectionError as exc:
        # Supabase unreachable is an outage, not a signed-out admin.
        raise _fail(status.HTTP_503_SERVICE_UNAVAILABLE, AdminAuthError.SUPABASE_UNAVAILABLE) from exc
    except (jwt.PyJWTError, jwt.PyJWKClientError) as exc:
        raise _fail(status.HTTP_401_UNAUTHORIZED, AdminAuthError.SESSION_INVALID) from exc
    if (claims.get("app_metadata") or {}).get("role") != ADMIN_ROLE:
        raise _fail(status.HTTP_403_FORBIDDEN, AdminAuthError.NOT_ADMIN)
    return Admin(user_id=claims["sub"], email=claims.get("email", ""))


async def require_admin(
    token: Annotated[str | None, Cookie(alias=ACCESS_COOKIE)] = None,
) -> Admin:
    if not token:
        raise _fail(status.HTTP_401_UNAUTHORIZED, AdminAuthError.SIGNED_OUT)
    return await verify_admin(token)


async def require_admin_header(
    marker: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> None:
    """A state-changing admin call must carry a custom header: a form cannot send one, and a
    cross-origin script cannot without a preflight, which only ADMIN_ORIGINS pass (app/core/cors.py).
    SameSite alone is not enough: every localhost port is the same site."""
    if marker != "1":
        raise _fail(status.HTTP_403_FORBIDDEN, AdminAuthError.CSRF_HEADER_MISSING)


async def _supabase_post(path: str, body: dict | None, bearer: str | None = None) -> httpx.Response:
    headers = {"apikey": get_settings().supabase_anon_key}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    try:
        async with httpx.AsyncClient(timeout=SUPABASE_TIMEOUT_SECONDS, transport=transport) as client:
            return await client.post(f"{_auth_base()}{path}", json=body, headers=headers)
    except httpx.HTTPError as exc:
        raise _fail(status.HTTP_503_SERVICE_UNAVAILABLE, AdminAuthError.SUPABASE_UNAVAILABLE) from exc


def _session_from(response: httpx.Response, failure: AdminAuthError) -> Session:
    if response.status_code in (400, 401, 403, 422):
        raise _fail(status.HTTP_401_UNAUTHORIZED, failure)
    if not response.is_success:
        raise _fail(status.HTTP_503_SERVICE_UNAVAILABLE, AdminAuthError.SUPABASE_UNAVAILABLE)
    payload = response.json()
    return Session(payload["access_token"], payload["refresh_token"], int(payload["expires_in"]))


async def sign_in(email: str, password: str) -> Session:
    response = await _supabase_post("/token?grant_type=password",
                                    {"email": email, "password": password})
    return _session_from(response, AdminAuthError.BAD_CREDENTIALS)


async def refresh(refresh_token: str) -> Session:
    response = await _supabase_post("/token?grant_type=refresh_token",
                                    {"refresh_token": refresh_token})
    return _session_from(response, AdminAuthError.SIGNED_OUT)


async def sign_out(access_token: str) -> None:
    """Revoke the session at Supabase. Best effort: the cookies are cleared either way."""
    try:
        await _supabase_post("/logout", None, bearer=access_token)
    except HTTPException:
        return


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
