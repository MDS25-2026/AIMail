"""Automated emails get no automatic draft, and Private mode never falls back to Gemini (drafting-skips.md)."""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app import email_policy, private_mode
from app.core.config import get_settings
from app.core.errors import DomainError, ErrorCode
from app.core.providers import Provider
from app.db.models import MaskingStatus, Message
from app.email_policy import Action, refusal_for


def _sql(clause) -> str:
    return str(clause.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def _email(**fields) -> Message:
    return Message(id=uuid4(), masking_status=MaskingStatus.COMPLETE, **fields)


def test_an_automated_email_gets_no_automatic_draft_but_regenerate_still_writes_one():
    newsletter = _email(is_automated=True)
    assert refusal_for(newsletter, Action.DRAFT) == ErrorCode.AUTOMATED_EMAIL
    assert refusal_for(newsletter, Action.REDRAFT) is None
    assert refusal_for(_email(is_automated=False), Action.DRAFT) is None


def test_the_background_drafter_skips_automated_emails(test_settings):
    assert "messages.is_automated IS false" in _sql(email_policy.drafting_filter())


@pytest.mark.parametrize("model, skips_private", [("", True), ("gemma4:e2b", False)])
def test_private_mode_owners_are_skipped_only_where_no_private_model_is_set_up(monkeypatch, test_settings, model,
                                                                              skips_private):
    monkeypatch.setenv("LOCAL_LLM_MODEL", model)
    get_settings.cache_clear()
    assert ("draft_provider" in _sql(email_policy.drafting_filter())) is skips_private


def test_private_mode_without_a_private_model_is_refused_never_sent_to_gemini(monkeypatch, test_settings):
    async def chose_local(_user_id):
        return Provider.LOCAL

    monkeypatch.setattr(private_mode, "provider_for", chose_local)
    monkeypatch.setenv("LOCAL_LLM_MODEL", "")
    get_settings.cache_clear()
    with pytest.raises(DomainError) as refused:
        asyncio.run(private_mode.model_for(uuid4()))
    assert refused.value.code == ErrorCode.PRIVATE_MODEL_UNAVAILABLE

    monkeypatch.setenv("LOCAL_LLM_MODEL", "gemma4:e2b")
    get_settings.cache_clear()
    assert asyncio.run(private_mode.model_for(uuid4())) == Provider.LOCAL


@pytest.mark.parametrize("offset, automated, shown", [(480, False, 480), (-240, False, -240), (0, False, None),
                                                      (480, True, None), (None, False, None)])
def test_the_recipients_local_time_is_only_offered_for_a_person_with_a_real_offset(offset, automated, shown):
    from app.dashboard import _sender_offset

    assert _sender_offset(_email(sender_utc_offset_minutes=offset, is_automated=automated)) == shown
