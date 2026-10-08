"""What an email may do (app/email_policy.py): one set of rules for every entry point."""

from datetime import datetime, timezone

import pytest
from sqlalchemy.dialects import postgresql

from app.core.errors import ErrorCode
from app.db.models import AuthStatus, MaskingStatus, Message
from app.email_policy import Action, drafting_filter, refusal_for

NOW = datetime(2026, 10, 8, tzinfo=timezone.utc)


def _message(**overrides) -> Message:
    fields = {"masking_status": MaskingStatus.COMPLETE, "auth_status": AuthStatus.PASS, "sent_at": None}
    return Message(**{**fields, **overrides})


@pytest.mark.parametrize("action", list(Action))
def test_a_clean_email_allows_everything(action):
    assert refusal_for(_message(), action) is None


@pytest.mark.parametrize("action", [Action.DRAFT, Action.REDRAFT, Action.REFINE])
def test_a_sent_email_keeps_its_draft(action):
    assert refusal_for(_message(sent_at=NOW), action) == ErrorCode.ALREADY_SENT


def test_a_repeat_send_is_left_to_the_send_claim_not_refused():
    assert refusal_for(_message(sent_at=NOW), Action.SEND) is None


@pytest.mark.parametrize("action", list(Action))
def test_a_quarantined_email_allows_nothing(action):
    assert refusal_for(_message(masking_status=MaskingStatus.PENDING), action) == ErrorCode.MASKING_PENDING


@pytest.mark.parametrize("action", [Action.DRAFT, Action.REDRAFT, Action.REFINE, Action.SEND])
def test_nothing_is_written_to_a_spoofer(action):
    assert refusal_for(_message(auth_status=AuthStatus.SPOOF_DETECTED), action) == ErrorCode.SENDER_UNVERIFIED


def test_a_spoofed_email_can_still_be_read_in_another_language():
    assert refusal_for(_message(auth_status=AuthStatus.SPOOF_DETECTED), Action.TRANSLATE) is None


@pytest.mark.parametrize("status", [AuthStatus.UNVERIFIED, AuthStatus.SENDER_CONFIRMED])
def test_an_unverified_or_confirmed_sender_is_drafted(status):
    assert refusal_for(_message(auth_status=status), Action.DRAFT) is None


def test_the_background_drafter_uses_the_same_rules():
    sql = str(drafting_filter().compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "sent_at IS NULL" in sql and "masking_status = 'complete'" in sql
    assert "auth_status IS DISTINCT FROM 'spoof_detected'" in sql
