"""Liveness and readiness for the backend and the agent, for a host's probes (no sign-in, no token).

/healthz answers while the process can serve at all; /readyz only once what it depends on is there,
so a host routes traffic to it. Neither says more than ok or which check failed.
"""

import asyncio
from collections.abc import Awaitable, Callable
from enum import StrEnum

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.session import get_engine

HEALTH_PATHS = frozenset({"/healthz", "/readyz"})
# A probe runs every few seconds; a slow database is reported as not ready, not waited on.
CHECK_TIMEOUT_SECONDS = 2.0
_UNAVAILABLE = 503


class CheckResult(StrEnum):
    OK = "ok"
    FAILED = "failed"


Check = Callable[[], Awaitable[bool]]


async def database_answers() -> bool:
    try:
        async with asyncio.timeout(CHECK_TIMEOUT_SECONDS), get_engine().connect() as connection:
            await connection.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError, TimeoutError):
        return False
    return True


async def model_configured() -> bool:
    """The agent can reach a model only with a Gemini key or a local model set; no call is made."""
    settings = get_settings()
    return bool(settings.google_api_key or settings.local_llm_model)


def health_router(checks: dict[str, Check]) -> APIRouter:
    router = APIRouter()

    @router.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": CheckResult.OK}

    @router.get("/readyz", include_in_schema=False)
    async def readyz() -> JSONResponse:
        results = {name: CheckResult.OK if await check() else CheckResult.FAILED for name, check in checks.items()}
        is_ready = all(result == CheckResult.OK for result in results.values())
        return JSONResponse({"status": CheckResult.OK if is_ready else CheckResult.FAILED, "checks": results},
                            status_code=200 if is_ready else _UNAVAILABLE)

    return router
