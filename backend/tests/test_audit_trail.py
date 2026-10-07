"""The audit trail (specs/features/sender-verification-and-audit.md): each person sees only their rows."""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app import audit_routes
from tests.conftest import API_TOKEN as TOKEN
from tests.test_account import ALICE, _signed_in, calls  # noqa: F401  (fixture)


def _row(user_id=None) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), created_at=datetime.now(timezone.utc), action="approve_and_send",
                           detail="message=1", success=True, prev_hash="0" * 64, current_hash="a" * 64,
                           user_id=user_id, is_valid=True)


@pytest.fixture
def audit_db(monkeypatch):
    """Records each query and its parameters; the chain summary says intact."""
    asked = []

    class _Result:
        def __init__(self, rows):
            self.rows = rows

        def one(self):
            return SimpleNamespace(is_intact=True, chained=1, head="a" * 64)

        def all(self):
            return self.rows

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def execute(self, statement, params=None):
            asked.append((str(statement), params))
            return _Result([_row(ALICE)])

    monkeypatch.setattr(audit_routes, "get_sessionmaker", lambda: _Session)
    return asked


def test_audit_without_a_token_is_refused(api_client):
    assert api_client.get("/audit").status_code == 401


def test_a_person_is_shown_only_their_own_rows(calls, audit_db):  # noqa: F811
    response = _signed_in().get("/audit")
    assert response.status_code == 200
    sql, params = audit_db[-1]
    assert "WHERE a.user_id = :uid" in sql and params["uid"] == ALICE
    # Rows with no owner are the whole system's; they once leaked to everyone.
    assert "IS NULL" not in sql


def test_a_script_sees_every_row(api_client, audit_db):
    response = api_client.get("/audit", headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 200
    sql, _params = audit_db[-1]
    assert "WHERE a.user_id" not in sql
    body = response.json()
    assert body["is_chain_intact"] is True and body["verified_records"] == 1 and body["head_hash"] == "a" * 64


def test_the_chain_is_checked_for_gaps_and_links_not_only_each_rows_own_hash():
    sql = audit_routes._CHAIN
    assert "lag(current_hash)" in sql and "lag(chain_seq)" in sql and "audit_row_hash(" in sql
