"""A dropped database connection must degrade, not crash the request.

Supabase's pooler closes connections mid-query. That surfaces as a bare `DBAPIError`, which the
OperationalError/InterfaceError handlers do not match — the guard existed but never fired, and
callers got a raw 500 with a stack trace. These pin both branches of the split.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import DBAPIError

from app.main import _database_error


def _app_raising(exc: Exception) -> TestClient:
    app = FastAPI()
    app.add_exception_handler(DBAPIError, _database_error)

    @app.get("/boom")
    async def boom() -> None:
        raise exc

    return TestClient(app, raise_server_exceptions=False)


def _dbapi_error(*, invalidated: bool) -> DBAPIError:
    exc = DBAPIError("SELECT 1", {}, Exception("connection was closed in the middle of operation"))
    exc.connection_invalidated = invalidated
    return exc


def test_lost_connection_becomes_a_retryable_503():
    res = _app_raising(_dbapi_error(invalidated=True)).get("/boom")
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "DATABASE_UNREACHABLE"


def test_a_genuine_sql_fault_is_not_reported_as_an_outage():
    # Ours to fix, not the database's fault — it must not masquerade as downtime.
    res = _app_raising(_dbapi_error(invalidated=False)).get("/boom")
    assert res.status_code == 500
    assert res.json()["error"]["code"] == "DATABASE_ERROR"


@pytest.mark.parametrize("invalidated", [True, False])
def test_the_response_never_leaks_the_failing_statement(invalidated):
    res = _app_raising(_dbapi_error(invalidated=invalidated)).get("/boom")
    assert "SELECT" not in res.text
