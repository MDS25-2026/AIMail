"""The public status page's data (specs/features/todo-redesign-and-status.md)."""

from datetime import datetime, timedelta, timezone

import pytest

from app import service_status
from app.service_status import PartState, listener_state

NOW = datetime(2026, 10, 12, 12, tzinfo=timezone.utc)


@pytest.mark.parametrize(("hours_ago", "state"), [
    (1, PartState.OK), (25, PartState.OK), (30, PartState.DEGRADED), (51, PartState.DOWN)])
def test_the_listener_is_judged_by_how_long_since_it_last_checked_in(hours_ago, state):
    assert listener_state(NOW - timedelta(hours=hours_ago), NOW) == state


def test_with_no_connected_mailbox_the_listener_is_never_called_working():
    assert listener_state(None, NOW) == PartState.DEGRADED


@pytest.fixture
def checks(monkeypatch):
    calls = {"presidio": 0}

    async def yes():
        return True

    async def presidio_down():
        calls["presidio"] += 1
        return False

    async def recent():
        return datetime.now(timezone.utc) - timedelta(minutes=5)

    monkeypatch.setattr(service_status, "database_answers", yes)
    monkeypatch.setattr(service_status, "presidio_answers", presidio_down)
    monkeypatch.setattr(service_status, "agent_answers", yes)
    monkeypatch.setattr(service_status, "newest_listener_check_in", recent)
    monkeypatch.setattr(service_status, "_cache", service_status._Cache())
    return calls


def test_a_signed_out_visitor_sees_each_part_and_one_failure_does_not_hide_the_rest(api_client, checks):
    response = api_client.get("/service-status")
    assert response.status_code == 200
    assert response.json()["parts"] == {"backend": "ok", "database": "ok", "masking": "down",
                                        "drafting": "ok", "listener": "ok"}


def test_visitors_within_the_cache_window_share_one_check(api_client, checks):
    for _ in range(5):
        api_client.get("/service-status")
    assert checks["presidio"] == 1
