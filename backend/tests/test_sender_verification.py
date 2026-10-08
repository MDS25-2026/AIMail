"""Sender verification (specs/features/sender-verification-and-audit.md): no draft or reply for a spoofer."""

import asyncio

import pytest

from app import dashboard
from app.core.ownership import EVERYTHING
from app.db.models import AuthStatus
from app.holding_reply import Refusal, refusal_on_arrival
from tests.test_holding_reply import _message, _settings
from tests.test_restorable_masking import mailbox  # noqa: F401  (fixture)


@pytest.fixture
def spoofed(mailbox):  # noqa: F811
    mailbox["message"].auth_status = AuthStatus.SPOOF_DETECTED
    mailbox["message"].generated_at = None
    mailbox["message"].sent_at = None
    return mailbox


def test_opening_a_spoofed_email_never_drafts_it(spoofed):
    email = asyncio.run(dashboard.email_detail(str(spoofed["message"].id), scope=EVERYTHING))
    assert email.authStatus == AuthStatus.SPOOF_DETECTED and spoofed["payloads"] == []


@pytest.mark.parametrize("action", ["regenerate", "refine"])
def test_a_spoofed_email_cannot_be_redrafted(spoofed, action):
    message_id = str(spoofed["message"].id)
    call = (dashboard.regenerate_email(message_id, scope=EVERYTHING) if action == "regenerate"
            else dashboard.refine_email(message_id, "warmer", "Hi.", scope=EVERYTHING))
    with pytest.raises(dashboard.DraftNotUpdatedError) as refused:
        asyncio.run(call)
    assert (refused.value.code, refused.value.status_code) == ("sender_unverified", 409)
    assert spoofed["payloads"] == []


def test_a_reply_to_a_spoofed_email_is_refused_at_send(spoofed):
    with pytest.raises(dashboard.SendRejectedError) as refused:
        asyncio.run(dashboard.approve_and_send(str(spoofed["message"].id), "Hi, noted.", scope=EVERYTHING))
    assert refused.value.code == "sender_unverified" and spoofed["sent"] == []


def test_a_spoofed_email_gets_no_holding_reply():
    message = _message(auth_status=AuthStatus.SPOOF_DETECTED)
    assert refusal_on_arrival(message, _settings(), "owner@example.com") == Refusal.SPOOFED


def test_a_confirmed_sender_is_drafted_again(spoofed, monkeypatch):
    updates, audited = [], []

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        def begin(self):
            return self

        def add(self, row):
            audited.append(row)

        async def execute(self, statement):
            updates.append(str(statement.compile(compile_kwargs={"literal_binds": True})))

    async def nothing(*_args, **_kwargs):
        return None

    monkeypatch.setattr(dashboard, "get_sessionmaker", lambda: _Session)
    monkeypatch.setattr(dashboard, "audit", nothing)
    email = asyncio.run(dashboard.confirm_sender(str(spoofed["message"].id), scope=EVERYTHING))
    assert email.authStatus == AuthStatus.SENDER_CONFIRMED
    # Only a flagged email moves, so a passing one is never relabelled.
    assert "messages.auth_status = 'spoof_detected'" in updates[0]
    # The audit row joins the same transaction as the change it records.
    assert [row.action for row in audited] == ["confirm_sender"]


def test_confirming_a_sender_that_passed_changes_nothing(mailbox):  # noqa: F811
    mailbox["message"].auth_status = AuthStatus.PASS
    email = asyncio.run(dashboard.confirm_sender(str(mailbox["message"].id), scope=EVERYTHING))
    assert email.authStatus == AuthStatus.PASS


def test_opening_an_undrafted_email_asks_the_worker_and_returns_at_once(spoofed, monkeypatch):
    spoofed["message"].auth_status = AuthStatus.PASS
    requested = []

    async def request_draft(pk):
        requested.append(pk)

    monkeypatch.setattr(dashboard, "request_draft", request_draft)
    email = asyncio.run(dashboard.email_detail(str(spoofed["message"].id), scope=EVERYTHING))
    assert email.isDrafting is True and requested == [spoofed["message"].id]
    assert spoofed["payloads"] == []  # the agent was not called inside the request


def test_a_spoofed_email_is_never_shown_as_being_drafted(spoofed, monkeypatch):
    requested = []

    async def request_draft(pk):
        requested.append(pk)

    monkeypatch.setattr(dashboard, "request_draft", request_draft)
    email = asyncio.run(dashboard.email_detail(str(spoofed["message"].id), scope=EVERYTHING))
    assert email.isDrafting is False and requested == []


def test_a_draft_that_failed_once_is_not_shown_as_coming(spoofed):
    message = spoofed["message"]
    message.auth_status, message.generation_attempts = AuthStatus.PASS, 1
    assert dashboard.is_drafting(message) is False  # the fast queue only makes the first attempt
