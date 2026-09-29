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
    Request,
    Response,
    status,
)
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError

from app.admin import stats
from app.admin.auth import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    Admin,
    AdminAuthError,
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
from app.core.constants import ADMIN_SIGN_IN_LIMIT, ADMIN_SIGN_IN_WINDOW_SECONDS
from app.core.ratelimit import RateLimiter
from app.db.session import get_sessionmaker

MAX_DAYS = 90
MAX_ROWS = 200

admin_app = FastAPI(title="AImail admin", docs_url=None, redoc_url=None, openapi_url=None)
rate_limit_sign_in = RateLimiter("admin sign-in", ADMIN_SIGN_IN_LIMIT, ADMIN_SIGN_IN_WINDOW_SECONDS)

AdminUser = Annotated[Admin, Depends(require_admin)]


async def _database_unreachable(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        content={"detail": "database_unreachable"})


for _error in (OSError, OperationalError, InterfaceError, DBAPIError):
    admin_app.add_exception_handler(_error, _database_unreachable)


@admin_app.post("/session", dependencies=[Depends(rate_limit_sign_in), Depends(require_admin_header)])
async def create_session(body: SignInRequest, response: Response) -> AdminIdentity:
    session = await sign_in(body.email, body.password)
    try:
        admin = await verify_admin(session.access_token)
    except HTTPException:
        # A real account without the admin role: end the session it was just given.
        await sign_out(session.access_token)
        raise
    set_session_cookies(response, session)
    return AdminIdentity(email=admin.email)


@admin_app.post("/session/refresh", dependencies=[Depends(require_admin_header)])
async def refresh_session(
    response: Response,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> AdminIdentity:
    if not refresh_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, AdminAuthError.SIGNED_OUT)
    session = await refresh(refresh_token)
    admin = await verify_admin(session.access_token)
    set_session_cookies(response, session)
    return AdminIdentity(email=admin.email)


@admin_app.delete("/session", status_code=status.HTTP_204_NO_CONTENT,
                  dependencies=[Depends(require_admin_header)])
async def delete_session(
    response: Response, access_token: Annotated[str | None, Cookie(alias=ACCESS_COOKIE)] = None
) -> None:
    if access_token:
        await sign_out(access_token)
    clear_session_cookies(response)


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
