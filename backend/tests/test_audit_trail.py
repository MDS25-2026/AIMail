"""Tests for user-facing tamper-evident audit trail route (#148 / PDPA)."""

from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from tests.conftest import API_TOKEN as TOKEN


@pytest.fixture
def client(api_client):
    return api_client


def test_audit_without_token_is_rejected(client):
    assert client.get("/audit").status_code == 401


def test_audit_with_wrong_token_is_rejected(client):
    res = client.get("/audit", headers={"Authorization": f"Bearer {TOKEN}invalid"})
    assert res.status_code == 401


def test_audit_passes_auth_gate(client):
    res = client.get("/audit", headers={"Authorization": f"Bearer {TOKEN}"})
    assert res.status_code != 401


def test_audit_response_with_mocked_db(client, monkeypatch):

    fake_id = uuid4()
    fake_ts = datetime.now(timezone.utc)
    mock_row = (
        fake_id,
        fake_ts,
        "store_message",
        "message stored securely",
        True,
        "0000000000000000000000000000000000000000000000000000000000000000",
        "1111111111111111111111111111111111111111111111111111111111111111",
        None,
        True,
    )

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def execute(self, stmt, params=None):
            mock_res = MagicMock()
            mock_res.fetchall.return_value = [mock_row]
            return mock_res

    import app.audit_routes as audit_routes_mod

    monkeypatch.setattr(
        audit_routes_mod, "get_sessionmaker", lambda: lambda: FakeSession()
    )

    res = client.get("/audit", headers={"Authorization": f"Bearer {TOKEN}"})
    assert res.status_code == 200
    data = res.json()
    assert data["is_chain_intact"] is True
    assert data["total_records"] == 1
    assert data["verified_records"] == 1
    assert len(data["events"]) == 1
    assert data["events"][0]["action"] == "store_message"
    assert (
        data["events"][0]["current_hash"]
        == "1111111111111111111111111111111111111111111111111111111111111111"
    )
