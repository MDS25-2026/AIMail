"""To-do redesign (specs/features/todo-redesign-and-status.md): order, snoozes and the start of today."""

from datetime import datetime, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy.dialects import postgresql

from app.contracts import DashboardEmail
from app.core.ownership import Scope
from app.todo import _open, _start_of_today, by_urgency


def _email(priority: str, timestamp: str) -> DashboardEmail:
    return DashboardEmail.model_construct(id=str(uuid4()), priority=priority, timestamp=timestamp)


def test_the_most_urgent_comes_first_then_the_longest_waiting():
    low_old = _email("low", "2026-10-01T00:00:00+00:00")
    critical_new = _email("critical", "2026-10-11T00:00:00+00:00")
    medium_old = _email("medium", "2026-10-02T00:00:00+00:00")
    medium_new = _email("medium", "2026-10-10T00:00:00+00:00")
    ordered = by_urgency([low_old, medium_new, critical_new, medium_old])
    assert ordered == [critical_new, medium_old, medium_new, low_old]


def test_a_snoozed_email_stays_off_the_lists_until_it_is_due():
    where = " ".join(str(c.compile(dialect=postgresql.dialect())) for c in _open(Scope(owner_id=uuid4())))
    assert "messages.snoozed_until IS NULL OR messages.snoozed_until <= now()" in where


def test_today_starts_at_midnight_where_the_reader_is_not_in_utc():
    start = _start_of_today("Asia/Kuala_Lumpur")
    local = start.astimezone(ZoneInfo("Asia/Kuala_Lumpur"))
    assert (local.hour, local.minute) == (0, 0)
    assert start <= datetime.now(timezone.utc)
    assert start.utcoffset().total_seconds() == 0
