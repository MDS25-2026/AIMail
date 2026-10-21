"""The audit trail is for admins (specs/features/admin-only-pages.md): everyone's rows, grouped and filtered."""

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
                           user_id=user_id, user_email="alice@gmail.com", email="alice@gmail.com", is_valid=True,
                           full_count=1, failed_count=0)


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


def _events_sql(asked: list) -> tuple[str, dict]:
    return next((sql, params) for sql, params in asked if "FROM audit_log a" in sql)


def test_audit_without_a_token_is_refused(api_client):
    assert api_client.get("/audit").status_code == 401


def test_to_anyone_but_an_admin_the_audit_trail_does_not_exist(calls, audit_db):  # noqa: F811
    response = _signed_in().get("/audit")
    assert response.status_code == 404 and response.json()["error"]["code"] == "not_found"
    assert audit_db == []


def test_an_admin_sees_everyones_rows_with_their_person_and_group(calls, audit_db):  # noqa: F811
    response = _signed_in(role="admin").get("/audit")
    assert response.status_code == 200
    sql, _params = _events_sql(audit_db)
    assert "WHERE" not in sql.split("FROM audit_log a")[1]
    event = response.json()["events"][0]
    assert event["userEmail"] == "alice@gmail.com" and event["group"] == "sending"
    assert [person["email"] for person in response.json()["people"]] == ["alice@gmail.com"]


def test_the_filters_become_bound_conditions(calls, audit_db):  # noqa: F811
    response = _signed_in(role="admin").get(
        "/audit", params={"group": "drafting", "person": str(ALICE), "failures_only": "true", "window": "week"})
    assert response.status_code == 200
    sql, params = _events_sql(audit_db)
    assert "a.action = ANY(:actions)" in sql and "generate_draft" in params["actions"]
    assert "a.user_id = :person" in sql and params["person"] == ALICE
    assert "a.success IS FALSE" in sql and "a.created_at >= :since" in sql
    assert 6.9 < (datetime.now(timezone.utc) - params["since"]).total_seconds() / 86400 < 7.1


def test_other_is_every_action_outside_the_named_groups(calls, audit_db):  # noqa: F811
    _signed_in(role="admin").get("/audit", params={"group": "other"})
    sql, params = _events_sql(audit_db)
    assert "NOT (a.action = ANY(:known))" in sql and "approve_and_send" in params["known"]


def test_a_script_sees_every_row(api_client, audit_db):
    response = api_client.get("/audit", headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 200
    body = response.json()
    assert body["isChainIntact"] is True and body["verifiedRecords"] == 1 and body["headHash"] == "a" * 64


def test_the_chain_is_checked_for_gaps_and_links_not_only_each_rows_own_hash():
    sql = audit_routes._CHAIN
    assert "lag(current_hash)" in sql and "lag(chain_seq)" in sql and "audit_row_hash(" in sql


@pytest.mark.parametrize(("is_valid", "verification"), [(True, "verified"), (False, "tampered"),
                                                        (None, "unverifiable")])
def test_a_row_that_could_not_be_checked_is_never_reported_as_verified(is_valid, verification):
    assert audit_routes._verification(is_valid) == verification


def test_structured_detail_is_returned_as_fields_and_old_prose_as_text():
    assert audit_routes._fields('{"message":"m1","restored":2}') == {"message": "m1", "restored": 2}
    assert audit_routes._fields("message=m1 restored=2") == {"text": "message=m1 restored=2"}
