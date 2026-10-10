"""Quiet hours, send later and snooze (specs/features/quiet-hours-send-later.md)."""

import asyncio
from datetime import datetime, time, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app import dashboard, quiet_hours_routes, scheduled_send_worker
from app.core.errors import DomainError, ErrorCode
from app.core.ownership import EVERYTHING
from app.db.models import MaskingStatus, Message
from app.gmail_send import SendError, SendOutcomeUnknownError
from app.quiet_hours import QuietHoursSettings, QuietHoursView
from app.scheduled_sends import CancelReason
from tests.test_account import ALICE, _signed_in, calls  # noqa: F401  (fixture)

NOW = datetime(2026, 10, 11, 1, 0, tzinfo=timezone.utc)
CLIENT = {"X-AIMail-Client": "1"}


def _held(**fields) -> SimpleNamespace:
    defaults = {"id": uuid4(), "message_id": uuid4(), "user_id": ALICE, "draft": "Thanks, [PERSON_1].",
                "send_at": NOW - timedelta(minutes=1), "created_at": NOW - timedelta(hours=2)}
    return SimpleNamespace(**(defaults | fields))


@pytest.fixture
def worker(monkeypatch):
    """The worker's database and send calls replaced by recorders."""
    state = {"due": [], "replied": False, "send_error": None, "claimable": True,
             "sent": [], "cancelled": [], "released": [], "claimed_cancel": []}

    async def due(_now):
        return state["due"]

    async def they_replied(_held):
        return state["replied"]

    async def claim(_schedule_id):
        return state["claimable"]

    async def send(message_id, draft, *, scope):
        if state["send_error"]:
            raise state["send_error"]
        state["sent"].append((message_id, draft, scope.owner_id))
        return SimpleNamespace(id=message_id)

    async def cancel(schedule_id, reason):
        state["cancelled"].append(reason)

    async def release(schedule_id):
        state["released"].append(schedule_id)

    async def cancel_claimed(schedule_id, reason):
        state["claimed_cancel"].append(reason)

    async def nothing(*_args, **_kwargs):
        return None

    for name, value in (("due", due), ("_they_replied", they_replied), ("claim", claim),
                        ("approve_and_send", send), ("cancel", cancel), ("release", release),
                        ("cancel_claimed", cancel_claimed), ("audit", nothing)):
        monkeypatch.setattr(scheduled_send_worker, name, value)
    monkeypatch.setattr(scheduled_send_worker, "datetime", SimpleNamespace(now=lambda tz: NOW))
    return state


def _run() -> int:
    return asyncio.run(scheduled_send_worker.send_due())


def test_a_due_reply_goes_out_once_through_the_normal_send_path(worker):
    held = _held()
    worker["due"] = [held]
    assert _run() == 1
    assert worker["sent"] == [(str(held.message_id), held.draft, ALICE)]


def test_a_reply_from_the_other_side_first_calls_the_send_off(worker):
    worker["due"], worker["replied"] = [_held()], True
    assert _run() == 0 and worker["sent"] == [] and worker["cancelled"] == [CancelReason.THEY_REPLIED]


def test_a_send_missed_by_over_an_hour_is_called_off_not_sent_late(worker):
    worker["due"] = [_held(send_at=NOW - timedelta(minutes=61))]
    assert _run() == 0 and worker["cancelled"] == [CancelReason.TOO_LATE]


def test_a_send_gmail_never_took_is_released_and_tried_again(worker):
    worker["due"], worker["send_error"] = [_held()], SendError("refused")
    assert _run() == 0 and len(worker["released"]) == 1 and worker["cancelled"] == []


def test_a_send_that_may_have_gone_out_keeps_its_claim(worker):
    worker["due"], worker["send_error"] = [_held()], SendOutcomeUnknownError("read timeout")
    assert _run() == 0 and worker["released"] == [] and worker["claimed_cancel"] == []


def test_a_send_the_checks_refuse_is_called_off_and_shown(worker):
    worker["due"] = [_held()]
    worker["send_error"] = dashboard.SendRejectedError(ErrorCode.REDACTION_MARKERS)
    assert _run() == 0 and worker["claimed_cancel"] == [CancelReason.REFUSED]


def test_another_worker_holding_the_claim_means_no_second_send(worker):
    worker["due"], worker["claimable"] = [_held()], False
    assert _run() == 0 and worker["sent"] == []


def _message(**fields) -> Message:
    defaults = {"id": uuid4(), "user_id": ALICE, "from_addr": "a@b.c", "subject": "Hi", "body_masked": "Hi",
                "masking_status": MaskingStatus.COMPLETE, "created_at": NOW}
    return Message(**(defaults | fields))


@pytest.fixture
def mailbox(monkeypatch):
    state = {"message": _message(), "held": [], "updates": []}

    async def load(pk, scope):
        return state["message"]

    async def details(message, thread):
        return dashboard.ThreadMap()

    async def no_thread(message):
        return []

    async def hold(message_id, user_id, draft, send_at):
        state["held"].append((draft, send_at))

    async def nothing(*_args, **_kwargs):
        return None

    async def no_states(_ids):
        return {}

    async def default_policy(_message):
        return dashboard.DEFAULT_POLICY

    for name, value in (("_load", load), ("_details_for", details), ("_thread_for", no_thread), ("hold", hold),
                        ("audit", nothing), ("states_for", no_states), ("_policy_for", default_policy)):
        monkeypatch.setattr(dashboard, name, value)
    return state


def test_a_reply_is_held_with_its_send_time_in_utc(mailbox):
    later = datetime.now(timezone(timedelta(hours=8))) + timedelta(hours=10)
    email = asyncio.run(dashboard.schedule_email(str(mailbox["message"].id), "Thanks.", later, scope=EVERYTHING))
    assert mailbox["held"] == [("Thanks.", later.astimezone(timezone.utc))]
    assert email is not None


@pytest.mark.parametrize("when", [timedelta(minutes=-5), timedelta(days=61)])
def test_a_send_time_in_the_past_or_too_far_ahead_is_refused(mailbox, when):
    with pytest.raises(DomainError) as refused:
        asyncio.run(dashboard.schedule_email(str(mailbox["message"].id), "Thanks.",
                                             datetime.now(timezone.utc) + when, scope=EVERYTHING))
    assert refused.value.code == ErrorCode.TIME_OUT_OF_RANGE and mailbox["held"] == []


def test_a_draft_that_could_not_be_sent_is_refused_when_scheduled_not_when_due(mailbox):
    with pytest.raises(dashboard.SendRejectedError) as refused:
        asyncio.run(dashboard.schedule_email(str(mailbox["message"].id), "Hi {{name}}",
                                             datetime.now(timezone.utc) + timedelta(hours=1), scope=EVERYTHING))
    assert refused.value.code == ErrorCode.UNRESOLVED_PLACEHOLDERS and mailbox["held"] == []


def test_quiet_hours_need_two_different_times_and_real_weekdays():
    view = QuietHoursView(start=time(21), end=time(8), weekendDays=[6, 5, 5], timezone="Asia/Kuala_Lumpur")
    assert view.weekendDays == [5, 6]
    for bad in ({"start": time(9), "end": time(9)}, {"weekendDays": [0]}, {"timezone": "Mars/Base"}):
        with pytest.raises(ValidationError):
            QuietHoursView(**({"start": time(21), "end": time(8), "weekendDays": [6, 7],
                               "timezone": "Asia/Kuala_Lumpur"} | bad))


def test_personal_quiet_hours_replace_the_company_default(calls, monkeypatch):  # noqa: F811
    saved = {}
    company = QuietHoursView(start=time(21), end=time(8), weekendDays=[6, 7], timezone="Asia/Kuala_Lumpur")

    async def save(user_id, view):
        saved[user_id] = view

    async def settings_for(user_id):
        personal = saved.get(user_id)
        return QuietHoursSettings(company=company, personal=personal, effective=personal or company)

    async def nothing(*_args, **_kwargs):
        return None

    for name, value in (("save", save), ("settings_for", settings_for), ("audit", nothing)):
        monkeypatch.setattr(quiet_hours_routes, name, value)
    response = _signed_in().put("/settings/quiet-hours", headers=CLIENT, json={
        "start": "22:00:00", "end": "07:00:00", "weekendDays": [5, 6], "timezone": "Asia/Kuala_Lumpur"})
    assert response.status_code == 200 and response.json()["effective"]["weekendDays"] == [5, 6]
    assert response.json()["company"]["weekendDays"] == [6, 7]
