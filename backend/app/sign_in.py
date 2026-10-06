"""Signing in to the dashboard with Google, through Supabase (docs/adr/0005).

The backend runs Supabase's OAuth-with-PKCE flow so the browser never holds a token: the code
verifier and the session both live in HttpOnly cookies.
"""

import base64
import hashlib
import logging
import secrets
from typing import Annotated
from urllib.parse import urlencode

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    Header,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app import connections
from app.core import supabase_auth
from app.core.auth import (
    CLIENT_HEADER,
    SESSION_COOKIE,
    AuthError,
    Principal,
    current_principal,
    scope_of_principal,
)
from app.core.config import get_settings
from app.core.supabase_auth import Session

router = APIRouter(prefix="/auth")
logger = logging.getLogger(__name__)

VERIFIER_COOKIE = "aimail_pkce"
VERIFIER_PATH = "/auth"
VERIFIER_MAX_AGE_SECONDS = 10 * 60
REFRESH_COOKIE = "aimail_session_refresh"
REFRESH_PATH = "/auth/session"
REFRESH_MAX_AGE_SECONDS = 7 * 24 * 60 * 60
SIGN_IN_FAILED = "sign_in_failed"
SIGN_IN_UNAVAILABLE = "sign_in_unavailable"
SIGN_IN_NOT_ALLOWED = "sign_in_not_allowed"
# Supabase's own descriptions are short and carry no tokens; capped so a log line stays one line.
MAX_LOGGED_DESCRIPTION = 200


class SessionInfo(BaseModel):
    email: str
    hasMailbox: bool


def _challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _back_to_sign_in(code: str) -> RedirectResponse:
    return RedirectResponse(f"{get_settings().dashboard_url}/signin?error={code}",
                            status_code=status.HTTP_303_SEE_OTHER)


def _set_session(response: Response, session: Session) -> None:
    secure = get_settings().admin_cookie_secure
    response.set_cookie(SESSION_COOKIE, session.access_token, max_age=session.expires_in, path="/",
                        httponly=True, secure=secure, samesite="strict")
    response.set_cookie(REFRESH_COOKIE, session.refresh_token, max_age=REFRESH_MAX_AGE_SECONDS,
                        path=REFRESH_PATH, httponly=True, secure=secure, samesite="strict")


def clear_session(response: Response) -> None:
    secure = get_settings().admin_cookie_secure
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, secure=secure, samesite="strict")
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH, httponly=True, secure=secure,
                           samesite="strict")


async def _require_client_header(
    marker: Annotated[str | None, Header(alias=CLIENT_HEADER)] = None,
) -> None:
    if marker != "1":
        raise HTTPException(status.HTTP_403_FORBIDDEN, AuthError.CLIENT_HEADER_MISSING)


@router.get("/google/start")
async def start_google_sign_in() -> RedirectResponse:
    try:
        base = supabase_auth.auth_base()
    except supabase_auth.SupabaseNotConfiguredError:
        return _back_to_sign_in(SIGN_IN_UNAVAILABLE)
    verifier = secrets.token_urlsafe(64)
    query = urlencode({
        "provider": "google",
        "redirect_to": f"{get_settings().backend_public_url}/auth/callback",
        "code_challenge": _challenge(verifier),
        "code_challenge_method": "s256",
        # Gmail read and send, connected in the same consent (per-user mailboxes). Offline with a
        # fresh consent is what makes Google issue a refresh token every time.
        "scopes": " ".join(connections.GMAIL_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    })
    response = RedirectResponse(f"{base}/authorize?{query}", status_code=status.HTTP_302_FOUND)
    # Lax, not Strict: the callback arrives as a cross-site redirect from Google and Supabase.
    response.set_cookie(VERIFIER_COOKIE, verifier, max_age=VERIFIER_MAX_AGE_SECONDS, path=VERIFIER_PATH,
                        httponly=True, secure=get_settings().admin_cookie_secure, samesite="lax")
    return response


@router.get("/callback")
async def finish_google_sign_in(
    code: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    verifier: Annotated[str | None, Cookie(alias=VERIFIER_COOKIE)] = None,
) -> RedirectResponse:
    if error:
        description = (error_description or "")[:MAX_LOGGED_DESCRIPTION]
        logger.warning("Google sign-in refused by Supabase: %s: %s", error, description)
        # Public sign-ups are off in Supabase, so a first-time Google user cannot be created.
        is_sign_up_refused = "signup" in description.lower().replace(" ", "")
        return _back_to_sign_in(SIGN_IN_NOT_ALLOWED if is_sign_up_refused else SIGN_IN_FAILED)
    if not code or not verifier:
        reason = "no code" if not code else "no PKCE verifier cookie (started on another host or port?)"
        logger.warning("Google sign-in callback with %s", reason)
        return _back_to_sign_in(SIGN_IN_FAILED)
    try:
        session = await supabase_auth.pkce_session(code, verifier)
    except supabase_auth.InvalidGrantError as exc:
        logger.warning("Supabase refused the Google sign-in code: %s", exc)
        return _back_to_sign_in(SIGN_IN_FAILED)
    except (supabase_auth.SupabaseUnavailableError, supabase_auth.SupabaseNotConfiguredError) as exc:
        logger.warning("Google sign-in could not reach Supabase: %s", exc)
        return _back_to_sign_in(SIGN_IN_UNAVAILABLE)
    await connections.connect_mailbox(session)
    response = RedirectResponse(get_settings().dashboard_url, status_code=status.HTTP_303_SEE_OTHER)
    _set_session(response, session)
    response.delete_cookie(VERIFIER_COOKIE, path=VERIFIER_PATH)
    return response


@router.get("/session")
async def current_session(principal: Annotated[Principal, Depends(current_principal)]) -> SessionInfo:
    return SessionInfo(email=principal.email, hasMailbox=await scope_of_principal(principal) is not None)


@router.post("/session/refresh", dependencies=[Depends(_require_client_header)])
async def refresh_current_session(
    response: Response,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> Response:
    if not refresh_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, AuthError.SIGNED_OUT)
    try:
        session = await supabase_auth.refresh_session(refresh_token)
    except supabase_auth.InvalidGrantError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, AuthError.SIGNED_OUT) from exc
    except (supabase_auth.SupabaseUnavailableError, supabase_auth.SupabaseNotConfiguredError) as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, AuthError.SUPABASE_UNAVAILABLE) from exc
    _set_session(response, session)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.delete("/session", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(_require_client_header)])
async def sign_out(request: Request, response: Response) -> Response:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        await supabase_auth.revoke(token)
    clear_session(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
