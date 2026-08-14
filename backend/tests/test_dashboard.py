from datetime import datetime, timezone
from uuid import uuid4

from app.contracts import priority_label
from app.dashboard import _to_email
from app.db.models import Message


def test_priority_label_maps_importance():
    assert priority_label(0) == "low"
    assert priority_label(1) == "medium"
    assert priority_label(2) == "high"
    assert priority_label(None) == "medium"


def test_to_email_maps_lane_a_and_b_fields():
    message = Message(
        id=uuid4(),
        from_addr="boss@company.com",
        subject="Q3 review",
        snippet_masked="Please review the deck by Friday.",
        received_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        importance=2,
        emails_masked=1,
        phones_masked=0,
    )
    email = _to_email(message)
    assert email.sender == "boss@company.com"
    assert email.subject == "Q3 review"
    assert email.priority == "high"
    assert email.piiMasked is True
    assert email.aiSummary == ""  # populated only by the detail endpoint


def test_email_detail_returns_none_for_bad_uuid():
    import asyncio

    from app.dashboard import email_detail

    assert asyncio.run(email_detail("not-a-uuid")) is None
