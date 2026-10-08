"""The admin console API, mounted at /admin (docs/adr/0004).

A separate FastAPI app, so the dashboard's shared-token dependency never applies here and admin
authentication is exactly one thing: a Supabase session in HttpOnly cookies, for a user whose
app_metadata grants the admin role. Everything but sign-in is read-only.
"""

from typing import Annotated

from fastapi import (
    Cookie,
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Response,
    status,
)

from app.admin import stats
from app.admin.auth import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    Admin,
    Session,
    clear_session_cookies,
    refresh,
    require_admin,
    require_admin_header,
    set_session_cookies,
    sign_in,
    sign_out,
    verify_admin,
)
from app.admin.schemas import (
    AdminIdentity,
    AuditEvent,
    FlaggedDraft,
    Overview,
    SignInRequest,
)
from app.audit import audit
from app.core.constants import ADMIN_SIGN_IN_LIMIT, ADMIN_SIGN_IN_WINDOW_SECONDS
from app.core.errors import DomainError, ErrorCode, register_error_handlers
from app.core.ratelimit import RateLimiter
from app.db.session import get_sessionmaker

MAX_DAYS = 90
MAX_ROWS = 200

admin_app = FastAPI(title="AImail admin", docs_url=None, redoc_url=None, openapi_url=None)
rate_limit_sign_in = RateLimiter("admin sign-in", ADMIN_SIGN_IN_LIMIT, ADMIN_SIGN_IN_WINDOW_SECONDS)

AdminUser = Annotated[Admin, Depends(require_admin)]


# The same split as the main app: an outage is a 503, a real SQL fault is logged and a 500.
register_error_handlers(admin_app)


@admin_app.post("/session", dependencies=[Depends(rate_limit_sign_in), Depends(require_admin_header)])
async def create_session(body: SignInRequest, response: Response) -> AdminIdentity:
    try:
        session = await sign_in(body.email, body.password)
        admin = await _admin_or_revoke(session)
    except HTTPException:
        await audit("admin_sign_in", "refused", success=False)
        raise
    set_session_cookies(response, session)
    await audit("admin_sign_in", f"admin={admin.user_id}")
    return AdminIdentity(email=admin.email)


async def _admin_or_revoke(session: Session) -> Admin:
    """The admin behind a fresh session. A real account without the role has the session it was
    just given revoked, and is told the same as a wrong password: the form must not confirm which
    passwords are valid."""
    try:
        return await verify_admin(session.access_token)
    except HTTPException as exc:
        await sign_out(session.access_token)
        raise DomainError(ErrorCode.INVALID_CREDENTIALS) from exc


@admin_app.post("/session/refresh", dependencies=[Depends(require_admin_header)])
async def refresh_session(
    response: Response,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> AdminIdentity:
    if not refresh_token:
        raise DomainError(ErrorCode.ADMIN_SIGNED_OUT)
    session = await refresh(refresh_token)
    admin = await verify_admin(session.access_token)
    set_session_cookies(response, session)
    return AdminIdentity(email=admin.email)


@admin_app.delete("/session", status_code=status.HTTP_204_NO_CONTENT,
                  dependencies=[Depends(require_admin_header)])
async def delete_session(
    response: Response,
    access_token: Annotated[str | None, Cookie(alias=ACCESS_COOKIE)] = None,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> None:
    """Revoke the session at Supabase, then clear the cookies. Once the hour-long access cookie
    has expired only the refresh token is left, so it is exchanged for one to revoke with; clearing
    the cookies alone would leave the refresh token valid at Supabase for a week."""
    token = access_token or await _access_from(refresh_token)
    if token:
        await sign_out(token)
    clear_session_cookies(response)


async def _access_from(refresh_token: str | None) -> str | None:
    if not refresh_token:
        return None
    try:
        return (await refresh(refresh_token)).access_token
    except HTTPException:
        return None  # already revoked or expired: nothing left to revoke


@admin_app.get("/session")
async def current_admin(admin: AdminUser) -> AdminIdentity:
    return AdminIdentity(email=admin.email)


@admin_app.get("/overview")
async def get_overview(
    admin: AdminUser, days: Annotated[int, Query(ge=1, le=MAX_DAYS)] = 7
) -> Overview:
    async with get_sessionmaker()() as session:
        return await stats.overview(session, days)


@admin_app.get("/audit")
async def get_audit(
    admin: AdminUser,
    limit: Annotated[int, Query(ge=1, le=MAX_ROWS)] = 100,
    failures_only: bool = False,
) -> list[AuditEvent]:
    async with get_sessionmaker()() as session:
        return await stats.audit_events(session, limit, failures_only)


@admin_app.get("/flagged")
async def get_flagged(
    admin: AdminUser, limit: Annotated[int, Query(ge=1, le=MAX_ROWS)] = 50
) -> list[FlaggedDraft]:
    async with get_sessionmaker()() as session:
        return await stats.flagged_drafts(session, limit)
