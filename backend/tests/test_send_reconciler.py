"""Settling sends whose outcome was lost (app/send_reconciler.py)."""

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app import send_reconciler
from app.db.models import Message


class _Session:
    def __init__(self, updates):
        self.updates = updates

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    def begin(self):
        return self

    async def execute(self, statement):
        self.updates.append(statement.compile().params)


@pytest.fixture
def settle(monkeypatch):
    updates, audited = [], []

    async def audit(action, **fields):
        audited.append(fields["outcome"])

    monkeypatch.setattr(send_reconciler, "get_sessionmaker", lambda: lambda: _Session(updates))
    monkeypatch.setattr(send_reconciler, "audit", audit)

    def run(found: str | None):
        async def ask(*_args, **_kwargs):
            return found

        monkeypatch.setattr(send_reconciler.gmail_send, "sent_message_in_thread_since", ask)
        message = Message(id=uuid4(), user_id=uuid4(), thread_id="t1", sent_at=datetime.now(timezone.utc))
        asyncio.run(send_reconciler._settle_reply(message))
        return updates, audited

    return run


def test_a_send_gmail_shows_is_recorded_as_done(settle):
    updates, audited = settle("gmail-id-1")
    assert updates[0]["sent_message_id"] == "gmail-id-1" and updates[0]["send_outcome_unknown_at"] is None
    assert audited == ["sent"]


def test_a_send_gmail_never_got_is_released_to_be_sent_again(settle):
    updates, audited = settle(None)
    assert updates[0]["sent_at"] is None and audited == ["not_sent"]


def test_only_a_send_marked_unknown_is_ever_reconciled():
    # An old sent row with no message id (sent before ids were recorded) must stay sent.
    for statement in (send_reconciler._unknown_replies(), send_reconciler._unknown_holding_replies()):
        sql = str(statement.compile(dialect=postgresql.dialect()))
        assert "send_outcome_unknown_at <" in sql


def test_a_gmail_failure_leaves_the_row_for_the_next_pass(monkeypatch):
    async def down():
        raise send_reconciler.httpx.ConnectError("offline")

    assert asyncio.run(send_reconciler._guarded(down(), uuid4())) == 0
