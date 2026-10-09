from datetime import datetime, timezone
from uuid import uuid4

from app.contracts import priority_label
from app.core.ownership import EVERYTHING
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

    assert asyncio.run(email_detail("not-a-uuid", scope=EVERYTHING)) is None


def test_quantities_in_the_body_reach_the_dashboard_in_both_systems():
    message = Message(id=uuid4(), body_masked="Ship 2,000 lb to the depot.",
                      created_at=datetime(2026, 8, 1, tzinfo=timezone.utc))
    (quantity,) = _to_email(message).quantities
    assert quantity.text == "2,000 lb" and quantity.system == "imperial"
    assert (quantity.metric.value, quantity.metric.unit) == (907.0, "kg")


def test_the_passages_a_draft_was_grounded_on_reach_the_dashboard():
    from app.dashboard import _source_records

    chunk_id = uuid4()
    records = _source_records([{"chunk_id": chunk_id, "content": "Refunds take 14 days.",
                                "similarity_score": 0.81234, "source_title": "Refund policy"}])
    message = Message(id=uuid4(), rag_sources=records,
                      created_at=datetime(2026, 8, 1, tzinfo=timezone.utc))
    (source,) = _to_email(message).sources
    assert source.label == "Refund policy" and source.chunkId == str(chunk_id)
    assert source.excerpt == "Refunds take 14 days." and source.score == 0.812


def test_an_email_generated_before_sources_were_stored_has_none():
    message = Message(id=uuid4(), created_at=datetime(2026, 8, 1, tzinfo=timezone.utc))
    assert _to_email(message).sources == []


def test_a_quarantined_message_is_shown_as_pending_with_no_content():
    from app.db.models import MaskingStatus

    message = Message(id=uuid4(), masking_status=MaskingStatus.PENDING,
                      created_at=datetime(2026, 8, 1, tzinfo=timezone.utc))
    email = _to_email(message)
    assert email.masking == "pending"
    assert email.body == "" and email.quantities == []


def test_a_quarantined_message_is_never_drafted(monkeypatch):
    import asyncio

    from app import dashboard
    from app.db.models import MaskingStatus

    async def must_not_run(*_args, **_kwargs):
        raise AssertionError("generation ran on a quarantined message")

    monkeypatch.setattr(dashboard, "_generate", must_not_run)
    for status in (MaskingStatus.PENDING, MaskingStatus.ABANDONED):
        message = Message(id=uuid4(), masking_status=status)
        assert asyncio.run(dashboard._generate_and_store(message)) is dashboard.GenerationOutcome.SKIPPED


def _at(hour: int) -> datetime:
    return datetime(2026, 9, 1, hour, tzinfo=timezone.utc)


def test_the_model_sees_earlier_thread_messages_by_position_never_by_sender():
    from app.dashboard import thread_context

    current = Message(id=uuid4(), received_at=_at(12), body_masked="Latest")
    earlier = Message(id=uuid4(), received_at=_at(9), from_addr="boss@company.com",
                      body_masked="Please send the Q3 figures.")
    later = Message(id=uuid4(), received_at=_at(15), body_masked="A later reply")
    context = thread_context(current, [earlier, later])
    assert context == "Earlier message 1:\nPlease send the Q3 figures."
    assert "boss@company.com" not in context


def test_the_dashboard_thread_lists_every_other_message():
    thread = [Message(id=uuid4(), from_addr="a@x.com", snippet_masked="First"),
              Message(id=uuid4(), from_addr="b@x.com", snippet_masked="Second")]
    message = Message(id=uuid4(), created_at=_at(12))
    shown = _to_email(message, thread=thread).threadContext
    assert [(m.sender, m.snippet) for m in shown] == [("a@x.com", "First"), ("b@x.com", "Second")]


def test_a_draft_that_fails_for_content_is_stored_as_not_drafted_so_it_is_not_retried(monkeypatch):
    import asyncio

    import httpx

    from app import dashboard

    async def no_chunks(*_args, **_kwargs):
        return []

    async def refuses(path, request, _answer=None):
        request = httpx.Request("POST", "http://agent/process-email")
        response = httpx.Response(422, json={"detail": "gemini_output_truncated"}, request=request)
        raise httpx.HTTPStatusError("422", request=request, response=response)

    async def no_audit(*_args, **_kwargs):
        return None

    monkeypatch.setattr(dashboard, "retrieve", no_chunks)
    monkeypatch.setattr(dashboard, "_call_agent", refuses)
    monkeypatch.setattr(dashboard, "audit", no_audit)

    async def stored(pk, fields):
        return True

    monkeypatch.setattr(dashboard, "_update_unsent", stored)
    from app.db.models import MaskingStatus

    message = Message(id=uuid4(), body_masked="Hi", masking_status=MaskingStatus.COMPLETE)
    asyncio.run(dashboard._generate_and_store(message))
    # Stored as handled (generated_at set), which is what stops the poller retrying it.
    assert message.generated_at is not None and message.needs_human_review is True
    assert message.critic_checks["review_reasons"] == ["no draft: gemini_output_truncated"]


def _send_harness(monkeypatch, claim: bool, send_error: bool = False):
    import asyncio

    from app import dashboard
    from app.gmail_send import SendError, SentReply

    calls = {"sent": 0, "released": 0}
    from app.db.models import MaskingStatus

    message = Message(id=uuid4(), from_addr="a@b.c", subject="Hi",
                      masking_status=MaskingStatus.COMPLETE,
                      created_at=datetime(2026, 9, 1, tzinfo=timezone.utc))

    async def load(pk, scope):
        return message

    async def claim_send(pk):
        return claim

    async def release(pk):
        calls["released"] += 1

    async def send_reply(*_args, **_kwargs):
        calls["sent"] += 1
        if send_error:
            raise SendError("gmail down")
        return SentReply(gmail_id="g", thread_id="t", message_id="<m>")

    async def no_audit(*_args, **_kwargs):
        return None

    for name, value in (("_load", load), ("_claim_send", claim_send),
                        ("_release_send_claim", release), ("send_reply", send_reply),
                        ("audit", no_audit)):
        monkeypatch.setattr(dashboard, name, value)
    return asyncio, dashboard, calls, message


def test_a_second_approval_that_loses_the_claim_never_sends(monkeypatch):
    import pytest

    from app.core.errors import DomainError, ErrorCode

    asyncio, dashboard, calls, message = _send_harness(monkeypatch, claim=False)
    with pytest.raises(DomainError) as refused:
        asyncio.run(dashboard.approve_and_send(str(message.id), "Thanks", scope=EVERYTHING))
    assert refused.value.code == ErrorCode.SEND_IN_PROGRESS and calls["sent"] == 0


def test_a_failed_send_releases_its_claim_so_it_can_be_approved_again(monkeypatch):
    import pytest

    from app.gmail_send import SendError

    asyncio, dashboard, calls, message = _send_harness(monkeypatch, claim=True, send_error=True)
    with pytest.raises(SendError):
        asyncio.run(dashboard.approve_and_send(str(message.id), "Thanks", scope=EVERYTHING))
    assert calls == {"sent": 1, "released": 1}


def test_a_regenerate_that_fails_for_content_keeps_the_existing_draft(monkeypatch):
    import asyncio

    from app import dashboard
    from app.db.models import MaskingStatus

    async def not_drafted(message, tone, thread, *_rest):
        return dashboard._not_drafted("gemini_output_truncated")

    async def must_not_write(pk, fields):
        raise AssertionError("a failed regenerate must not overwrite the draft")

    monkeypatch.setattr(dashboard, "_generate", not_drafted)
    monkeypatch.setattr(dashboard, "_update_unsent", must_not_write)
    message = Message(id=uuid4(), masking_status=MaskingStatus.COMPLETE, draft_reply="Reviewed draft")
    outcome = asyncio.run(dashboard._generate_and_store(message, tone="casual"))
    assert outcome is dashboard.GenerationOutcome.KEPT
    assert message.draft_reply == "Reviewed draft"


def test_the_view_shows_the_tone_the_draft_was_written_in():
    casual = Message(id=uuid4(), draft_reply="Hey!", draft_tone="casual", created_at=datetime(2026, 10, 8, tzinfo=timezone.utc))
    older = Message(id=uuid4(), draft_reply="Dear", created_at=datetime(2026, 10, 8, tzinfo=timezone.utc))
    assert _to_email(casual).tone == "casual"
    assert _to_email(older).tone == "professional"  # written before tones were stored
