"""An email returned after a change keeps its details, so the view's Show details switch stays (test run T14)."""

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from app import dashboard
from app.core.vault import ThreadMap
from app.db.models import MaskingStatus, Message


def _message() -> Message:
    return Message(id=uuid4(), user_id=uuid4(), subject="Invoice", masking_status=MaskingStatus.COMPLETE,
                   from_addr="Aisyah <a@client.com>", received_at=datetime.now(timezone.utc))


def test_an_email_returned_after_scheduling_or_cancelling_keeps_its_details(monkeypatch):
    details = ThreadMap()
    details.add_sender("Aisyah")

    async def policy(_message):
        return dashboard.DEFAULT_POLICY

    async def no_schedules(_ids):
        return {}

    async def no_thread(_message):
        return []

    async def thread_details(_message, _thread):
        return details

    monkeypatch.setattr(dashboard, "_policy_for", policy)
    monkeypatch.setattr(dashboard, "states_for", no_schedules)
    monkeypatch.setattr(dashboard, "_thread_for", no_thread)
    monkeypatch.setattr(dashboard, "_details_for", thread_details)
    email = asyncio.run(dashboard._with_schedule(_message()))
    assert [detail.value for detail in email.details] == ["Aisyah"]
