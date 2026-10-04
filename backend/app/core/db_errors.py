"""Database failures as clean HTTP answers, shared by the main app and the mounted admin app."""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError

logger = logging.getLogger(__name__)


async def _database_unreachable(request: Request, exc: Exception) -> JSONResponse:
    # DB connection failures (raw OSError / SQLAlchemy connect errors) become a clean 503 instead
    # of a raw 500 stack trace — usually a wrong DATABASE_URL or a paused Supabase project.
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error": {
                "code": "DATABASE_UNREACHABLE",
                "message": (
                    "Cannot reach the database. Check DATABASE_URL (use the Supabase Session "
                    "pooler, not the direct IPv6 host) and that the Supabase project is not paused."
                ),
            }
        },
    )


async def _database_error(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for DBAPI failures, split by whether the connection survived.

    A connection dropped mid-query by the Supabase pooler surfaces as a bare `DBAPIError`, not
    `OperationalError`, so the handler above never fired and the caller got a raw 500. Deciding on
    `connection_invalidated` keeps that distinction honest: a lost connection is a 503 worth
    retrying, while a genuine SQL fault is our bug and must not masquerade as an outage.
    """
    if getattr(exc, "connection_invalidated", False):
        return await _database_unreachable(request, exc)
    logger.exception("database error on %s", request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": {"code": "DATABASE_ERROR", "message": "The database rejected a query."}},
    )


def register_database_handlers(app: FastAPI) -> None:
    for exc_type in (OSError, OperationalError, InterfaceError):
        app.add_exception_handler(exc_type, _database_unreachable)
    # Registered after the specific handlers so those still win for their own types.
    app.add_exception_handler(DBAPIError, _database_error)
