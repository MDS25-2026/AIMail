"""Opening an email shows the same priority as its row in the inbox: both apply the owner's rules."""

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from app import dashboard
from app.db.models import Message
from app.personalisation import Policy
from tests.conftest import REAL_POLICY_FOR


def _message(**fields: object) -> Message:
    return Message(id=uuid4(), from_addr="Boss <boss@corp.com>", importance=0,
                   created_at=datetime(2026, 10, 10, tzinfo=timezone.utc), **fields)


def test_a_sender_rule_shows_in_the_detail_view_as_it_does_in_the_list():
    rules = Policy(sender_rules={"boss@corp.com": 2})
    assert dashboard._to_email(_message(), rules).priority == "high"


def test_the_detail_view_uses_the_owners_rules(test_settings, monkeypatch):
    owner = uuid4()
    asked = []

    async def for_user(_session, user_id):
        asked.append(user_id)
        return Policy(sender_rules={"boss@corp.com": 2})

    monkeypatch.setattr(dashboard, "load_policy_for_user", for_user)
    policy = asyncio.run(REAL_POLICY_FOR(_message(user_id=owner)))
    assert asked == [owner] and policy.sender_rules == {"boss@corp.com": 2}


def test_an_unowned_email_uses_the_original_mailboxs_rules_as_the_list_does(test_settings, monkeypatch):
    asked = []

    async def by_email(_session, email):
        asked.append(email)
        return Policy()

    monkeypatch.setattr(dashboard, "load_policy", by_email)
    monkeypatch.setattr(dashboard.mailbox, "owner", lambda: "owner@corp.com")
    asyncio.run(REAL_POLICY_FOR(_message(user_id=None)))
    assert asked == ["owner@corp.com"]
