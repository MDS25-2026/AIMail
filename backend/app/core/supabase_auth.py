"""Supabase Auth plumbing shared by the admin console (ADR 0004) and dashboard sign-in (ADR 0005).

Tokens are verified locally against the project's published ES256 keys; nothing here holds a
secret. Failures are plain exceptions so each caller maps them to its own HTTP error codes.
"""

import asyncio
import math
import time
from dataclasses import dataclass, field
from functools import lru_cache

import httpx
import jwt

from app.core.config import get_settings

AUDIENCE = "authenticated"
ALGORITHMS = ["ES256"]
JWKS_CACHE_SECONDS = 600
JWKS_REFETCH_SECONDS = 60
SUPABASE_TIMEOUT_SECONDS = 10.0
INVALID_GRANT_STATUSES = (400, 401, 403, 422)

# Tests swap this for httpx.MockTransport.
transport: httpx.AsyncBaseTransport | None = None


class SupabaseNotConfiguredError(RuntimeError):
    """SUPABASE_URL or SUPABASE_ANON_KEY is unset, so sign-in is refused (fail closed)."""


class SupabaseUnavailableError(RuntimeError):
    """Supabase could not be reached: an outage, not a signed-out user."""


class InvalidTokenError(RuntimeError):
    """An access token that is forged, expired, or for another project."""


class InvalidGrantError(RuntimeError):
    """Supabase refused the credentials, refresh token or code."""


@dataclass(frozen=True)
class Session:
    access_token: str
    refresh_token: str
    expires_in: int
    user_id: str = ""
    email: str = ""
    # Present after an OAuth sign-in that asked the provider for offline access (Google).
    provider_token: str | None = None
    provider_refresh_token: str | None = None
    # The response's field names, never values: says what Supabase sent when a token is missing.
    fields: tuple[str, ...] = field(default=(), repr=False)


def auth_base() -> str:
    settings = get_settings()
    if not (settings.supabase_url and settings.supabase_anon_key):
        raise SupabaseNotConfiguredError("SUPABASE_URL and SUPABASE_ANON_KEY are required")
    return settings.supabase_url.rstrip("/") + "/auth/v1"


class _KeySet:
    """The project's signing keys by key id, refetched on an unknown id at most once a minute.

    PyJWKClient refetches on every unknown kid, so a stream of forged cookies would each cost a
    blocking fetch to Supabase. A real key rotation still lands within JWKS_REFETCH_SECONDS.
    """

    def __init__(self, base: str) -> None:
        self._client = jwt.PyJWKClient(f"{base}/.well-known/jwks.json", cache_keys=False)
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
def _jwks(base: str) -> _KeySet:
    return _KeySet(base)


def _decode(token: str, base: str) -> dict:
    key = _jwks(base).get_signing_key_from_jwt(token).key
    return jwt.decode(token, key, algorithms=ALGORITHMS, audience=AUDIENCE, issuer=base,
                      options={"require": ["exp", "sub", "aud", "iss"]})


async def verify_access_token(token: str) -> dict:
    """The verified claims of a Supabase access token."""
    base = auth_base()
    try:
        # The JWKS fetch is blocking the first time and every JWKS_CACHE_SECONDS after.
        return await asyncio.to_thread(_decode, token, base)
    except jwt.PyJWKClientConnectionError as exc:
        raise SupabaseUnavailableError(str(exc)) from exc
    except (jwt.PyJWTError, jwt.PyJWKClientError) as exc:
        raise InvalidTokenError(str(exc)) from exc


async def supabase_post(path: str, body: dict | None, bearer: str | None = None) -> httpx.Response:
    headers = {"apikey": get_settings().supabase_anon_key}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    try:
        async with httpx.AsyncClient(timeout=SUPABASE_TIMEOUT_SECONDS, transport=transport) as client:
            return await client.post(f"{auth_base()}{path}", json=body, headers=headers)
    except httpx.HTTPError as exc:
        raise SupabaseUnavailableError(str(exc)) from exc


def session_from(response: httpx.Response) -> Session:
    # Supabase answers 401 for a wrong apikey too; that is our configuration, not the user's code.
    if response.status_code == 401 and "api key" in response.text.lower():
        raise SupabaseNotConfiguredError("Supabase rejected SUPABASE_ANON_KEY as an invalid API key")
    if response.status_code in INVALID_GRANT_STATUSES:
        raise InvalidGrantError(f"Supabase refused with {response.status_code}")
    if not response.is_success:
        raise SupabaseUnavailableError(f"Supabase answered {response.status_code}")
    payload = response.json()
    user = payload.get("user") or {}
    return Session(
        payload["access_token"], payload["refresh_token"], int(payload["expires_in"]),
        user_id=user.get("id", ""), email=user.get("email", ""),
        provider_token=payload.get("provider_token"),
        provider_refresh_token=payload.get("provider_refresh_token"),
        fields=tuple(sorted(payload)),
    )


async def password_session(email: str, password: str) -> Session:
    return session_from(await supabase_post("/token?grant_type=password",
                                            {"email": email, "password": password}))


async def refresh_session(refresh_token: str) -> Session:
    return session_from(await supabase_post("/token?grant_type=refresh_token",
                                            {"refresh_token": refresh_token}))


async def pkce_session(auth_code: str, code_verifier: str) -> Session:
    """The session for an OAuth code, proven by the verifier only this browser holds."""
    return session_from(await supabase_post("/token?grant_type=pkce",
                                            {"auth_code": auth_code, "code_verifier": code_verifier}))


async def revoke(access_token: str) -> None:
    """Revoke the session at Supabase. Best effort: callers clear their cookies either way."""
    try:
        await supabase_post("/logout", None, bearer=access_token)
    except (SupabaseUnavailableError, SupabaseNotConfiguredError):
        return
