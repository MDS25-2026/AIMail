"""Holding replies (specs/features/holding-reply.md): the user's own words, only when they would
want them sent. Each test is one condition from the spec's acceptance criteria."""

import asyncio
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from app import holding_reply_scheduler as scheduler
from app.core.language import Language, detect_language
from app.db.models import HoldingReply, HoldingReplySettings, MaskingStatus, Message
from app.holding_reply import (
    InvalidSettingsError,
    Refusal,
    SettingsBody,
    SettingsError,
    choose_language,
    is_active,
    refusal_on_arrival,
    render,
    validate,
)

OWNER = UUID("aaaaaaaa-0000-4000-8000-000000000001")
KL = timezone(timedelta(hours=8))
# Monday 6 October 2026, 21:00 in Kuala Lumpur: after hours.
EVENING = datetime(2026, 10, 5, 21, 0, tzinfo=KL)
MORNING = datetime(2026, 10, 5, 10, 0, tzinfo=KL)


def _settings(**overrides) -> HoldingReplySettings:
    values = {"user_id": OWNER, "enabled": True, "enabled_at": datetime(2026, 10, 1, tzinfo=timezone.utc),
                  "active_when": "outside_hours", "work_days": [1, 2, 3, 4, 5], "work_start": time(9), "work_end": time(18),
                  "timezone": "Asia/Kuala_Lumpur", "leave_from": None, "leave_until": None, "audience": "everyone",
                  "scope": "all", "cooldown_days": 4, "templates": {"en": "Hi {name}, I'll reply tomorrow."},
                  "default_language": "en"}
    return HoldingReplySettings(**{**values, **overrides})


def _message(**overrides) -> Message:
    values = {"id": uuid4(), "user_id": OWNER, "from_addr": "Aisyah Rahman <aisyah@client.com>", "reply_to": None,
                  "received_at": EVENING, "masking_status": MaskingStatus.COMPLETE, "is_automated": False,
                  "body_masked": "Hi, can you send the invoice?", "thread_id": "t1", "gmail_message_id": "g1",
                  "sent_at": None, "generated_at": EVENING, "draft_reply": "Sure."}
    return Message(**{**values, **overrides})


# ---------- Settings ----------

@pytest.mark.parametrize(("change", "code"), [
    ({"templates": {"en": "Hi {nmae}"}}, SettingsError.UNKNOWN_PLACEHOLDER),
    ({"templates": {"en": "Back on {return_date}"}}, SettingsError.RETURN_DATE_NEEDS_LEAVE),
    ({"templates": {"en": "   "}}, SettingsError.EMPTY_TEMPLATE),
    ({"enabled": True, "templates": {"ms": "Terima kasih"}}, SettingsError.NO_DEFAULT_TEMPLATE),
    ({"timezone": "Mars/Olympus"}, SettingsError.UNKNOWN_TIMEZONE),
    ({"activeWhen": "leave"}, SettingsError.LEAVE_NEEDS_DATES),
    ({"workStart": time(18), "workEnd": time(9)}, SettingsError.WORKDAY_ENDS_BEFORE_IT_STARTS),
    ({"leaveFrom": date(2026, 10, 9), "leaveUntil": date(2026, 10, 1)}, SettingsError.LEAVE_ENDS_BEFORE_IT_STARTS),
    ({"workDays": [0, 8]}, SettingsError.BAD_WORK_DAYS),
])
def test_settings_that_could_never_work_are_refused_with_a_reason(change, code):
    with pytest.raises(InvalidSettingsError) as caught:
        validate(SettingsBody(**{"templates": {"en": "Hi"}, **change}))
    assert caught.value.code == code


def test_a_return_date_is_allowed_once_leave_dates_are_set():
    validate(SettingsBody(enabled=True, templates={"en": "Back on {return_date}"},
                          leaveFrom=date(2026, 10, 1), leaveUntil=date(2026, 10, 15)))


# ---------- When it is active ----------

def test_outside_working_hours_means_evenings_and_weekends_in_the_users_timezone():
    settings = _settings()
    assert is_active(settings, EVENING) and not is_active(settings, MORNING)
    assert is_active(settings, datetime(2026, 10, 10, 10, tzinfo=KL))  # Saturday morning
    # 03:00 UTC is 11:00 in Kuala Lumpur: working hours, whatever the server's clock says.
    assert not is_active(settings, datetime(2026, 10, 5, 3, tzinfo=timezone.utc))


def test_leave_covers_the_whole_day_including_working_hours():
    settings = _settings(active_when="leave", leave_from=date(2026, 10, 5), leave_until=date(2026, 10, 9))
    assert is_active(settings, MORNING)
    assert not is_active(settings, datetime(2026, 10, 12, 21, tzinfo=KL))


# ---------- Conditions on arrival ----------

def test_an_ordinary_email_after_hours_qualifies():
    assert refusal_on_arrival(_message(), _settings(), "me@corp.com") is None


@pytest.mark.parametrize(("message_change", "settings_change", "refusal"), [
    ({}, {"enabled": False}, Refusal.DISABLED),
    ({"received_at": datetime(2026, 9, 1, tzinfo=timezone.utc)}, {}, Refusal.BEFORE_ENABLED),
    ({"masking_status": MaskingStatus.PENDING}, {}, Refusal.MASKING_PENDING),
    ({"is_automated": True}, {}, Refusal.AUTOMATED),
    ({"body_masked": "Verify your account at secure-bank.example/verify"}, {}, Refusal.PHISHING),
    ({"reply_to": "someone.else@elsewhere.com"}, {}, Refusal.REPLY_TO_DIFFERS),
    ({"received_at": MORNING}, {}, Refusal.NOT_ACTIVE),
    ({}, {"audience": "domain"}, Refusal.OUTSIDE_DOMAIN),
    ({"from_addr": "Me <me@corp.com>"}, {}, Refusal.NO_SENDER),
])
def test_each_always_on_rail_stops_a_holding_reply(message_change, settings_change, refusal):
    assert refusal_on_arrival(_message(**message_change), _settings(**settings_change), "me@corp.com") == refusal


# ---------- The words ----------

def test_the_template_is_filled_in_locally_with_the_senders_name_and_return_date():
    text = render("Hi {name}, back on {return_date}.", Language.EN, "Aisyah Rahman <a@x.com>", date(2026, 10, 15))
    assert text == "Hi Aisyah Rahman, back on 15 October 2026."
    assert render("Kembali {return_date}", Language.MS, "a@x.com", date(2026, 10, 15)) == "Kembali 15 Oktober 2026"
    assert render("{return_date}回来", Language.ZH, "a@x.com", date(2026, 10, 15)) == "2026年10月15日回来"


def test_a_sender_with_no_display_name_gets_a_plain_greeting_never_their_address():
    assert render("Hi {name},", Language.EN, "aisyah@client.com", None) == "Hi there,"
    assert render("Salam {name},", Language.MS, "<aisyah@client.com>", None) == "Salam tuan/puan,"


def test_the_senders_language_is_used_when_there_is_a_template_for_it():
    settings = _settings(templates={"en": "Hi", "zh": "您好"})
    assert choose_language(detect_language("您好，请问发票什么时候到？"), settings) == Language.ZH
    assert choose_language(detect_language("Saya ingin tahu dan terima kasih"), settings) == Language.EN


# ---------- When it falls due ----------

def _due(**message_change) -> scheduler.Due:
    reply = HoldingReply(id=uuid4(), user_id=OWNER, message_id=uuid4(), recipient_addr="aisyah@client.com",
                         language="en", scheduled_for=EVENING + timedelta(minutes=10))
    return scheduler.Due(reply=reply, message=_message(**message_change), settings=_settings(audience="correspondents"),
                         owner_email="me@corp.com")


@pytest.fixture
def world(monkeypatch):
    state = {"counts": [0, 0], "replied": False, "written": True, "gmail_error": None, "sent": [], "agent_calls": 0}

    async def count(_stmt):
        return state["counts"].pop(0) if state["counts"] else 0

    async def replied(thread_id, since, *, owner_id):
        if state["gmail_error"]:
            raise state["gmail_error"]
        return state["replied"]

    async def written(address, *, owner_id):
        return state["written"]

    async def send_reply(gmail_id, to, subject, body, *, owner_id, extra_headers=None):
        state["sent"].append((body, extra_headers))
        return type("Sent", (), {"message_id": "<m>"})()

    async def nothing(*_args, **_kwargs):
        return None

    async def claim(_reply_id):
        return True

    monkeypatch.setattr(scheduler, "_count", count)
    monkeypatch.setattr(scheduler.gmail_send, "replied_in_thread_since", replied)
    monkeypatch.setattr(scheduler.gmail_send, "has_written_to", written)
    monkeypatch.setattr(scheduler.gmail_send, "send_reply", send_reply)
    monkeypatch.setattr(scheduler, "audit", nothing)
    monkeypatch.setattr(scheduler, "_claim", claim)
    monkeypatch.setattr(scheduler, "get_sessionmaker", lambda: lambda: _NoSession())
    return state


class _NoSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    def begin(self):
        return self

    async def execute(self, _statement):
        return None


NOW = EVENING + timedelta(minutes=11)


def _verdict(due, now=NOW):
    return asyncio.run(scheduler.verdict_when_due(due, now))


def test_a_due_reply_with_every_condition_met_is_sent(world):
    assert _verdict(_due()) == scheduler.Verdict.SEND


def test_a_reply_the_user_sent_from_gmail_meanwhile_cancels_it(world):
    world["replied"] = True
    assert _verdict(_due()) == Refusal.USER_REPLIED


def test_a_reply_sent_through_aimail_meanwhile_cancels_it(world):
    assert _verdict(_due(sent_at=NOW)) == Refusal.USER_REPLIED


def test_a_sender_the_user_has_never_written_to_gets_nothing_by_default(world):
    world["written"] = False
    assert _verdict(_due()) == Refusal.NOT_CORRESPONDENT


def test_a_sender_answered_within_the_cooldown_gets_nothing(world):
    world["counts"] = [0, 1]  # sent today, then sent to this sender within the cooldown
    assert _verdict(_due()) == Refusal.COOLDOWN


def test_the_daily_cap_stops_further_replies(world):
    world["counts"] = [50, 0]
    assert _verdict(_due()) == Refusal.DAILY_CAP


def test_an_email_the_router_judged_needs_no_reply_gets_none(world):
    due = _due(draft_reply="")
    due.settings.scope = "needs_reply"
    assert _verdict(due) == Refusal.NO_REPLY_NEEDED


def test_drafting_not_finished_waits_and_gmail_trouble_waits_too(world):
    due = _due(generated_at=None)
    due.settings.scope = "needs_reply"
    assert _verdict(due) == scheduler.Verdict.WAIT
    world["gmail_error"] = scheduler.httpx.ConnectError("down")
    assert _verdict(_due()) == scheduler.Verdict.WAIT


def test_a_reply_that_could_not_go_out_in_time_is_cancelled_not_sent_late(world):
    assert _verdict(_due(), now=EVENING + timedelta(hours=2)) == Refusal.STALE


def test_settings_switched_off_before_it_falls_due_cancel_it(world):
    due = _due()
    due.settings.enabled = False
    assert _verdict(due) == Refusal.DISABLED


def test_what_goes_out_is_exactly_the_users_words_marked_as_an_auto_reply(world, monkeypatch):
    def no_agent(*_args, **_kwargs):
        raise AssertionError("a holding reply must never reach the AI")

    monkeypatch.setattr("app.dashboard._call_agent", no_agent)
    asyncio.run(scheduler._send(_due()))
    body, headers = world["sent"][0]
    assert body == "Hi Aisyah Rahman, I'll reply tomorrow."
    assert headers["Auto-Submitted"] == "auto-replied"
