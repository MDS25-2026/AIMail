"""Dismissing from the To-do page leaves an audit row, as snoozing does (known-issues.md)."""

from uuid import uuid4

import pytest

from app import todo_routes
from app.audit import AuditAction
from tests.conftest import AUTH_HEADERS


@pytest.fixture
def audited(monkeypatch):
    rows = []

    async def changed(*_args, **_kwargs):
        return True

    async def audit(action, **fields):
        rows.append((action, fields))

    for name in ("dismiss_email", "dismiss_waiting"):
        monkeypatch.setattr(todo_routes, name, changed)
    monkeypatch.setattr(todo_routes, "audit", audit)
    return rows


def test_dismissing_an_email_and_bringing_it_back_are_both_audited(api_client, audited):
    email = uuid4()
    assert api_client.post(f"/emails/{email}/dismiss", headers=AUTH_HEADERS).status_code == 204
    assert api_client.delete(f"/emails/{email}/dismiss", headers=AUTH_HEADERS).status_code == 204
    assert [(action, fields["dismissed"]) for action, fields in audited] == [
        (AuditAction.EMAIL_DISMISSED, True), (AuditAction.EMAIL_DISMISSED, False)]
    assert audited[0][1]["message"] == email


def test_not_waiting_on_a_reply_is_audited(api_client, audited):
    sent = uuid4()
    assert api_client.post(f"/todo/waiting/{sent}/dismiss", headers=AUTH_HEADERS).status_code == 204
    assert audited == [(AuditAction.WAITING_DISMISSED, {"user_id": None, "sent": sent})]
