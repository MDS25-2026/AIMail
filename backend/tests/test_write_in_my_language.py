"""Write in my language, send in theirs (specs/features/write-in-my-language.md)."""

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest

from app import dashboard
from app.core.errors import ErrorCode
from app.core.vault import ThreadMap
from app.db.models import MaskingStatus, Message


@pytest.fixture
def email(monkeypatch):
    message = Message(id=uuid4(), user_id=uuid4(), subject="Invoice", masking_status=MaskingStatus.COMPLETE,
                      body_masked="Hi, could you confirm the invoice date? Thanks, [PERSON_1]",
                      received_at=datetime.now(timezone.utc))
    details = ThreadMap()
    details.add_message(str(message.id), {"[PERSON_1]": "Aisyah"}, message.body_masked)
    state = {"sent": []}

    async def loaded(_pk, _scope):
        return message, []

    async def thread_details(_message, _thread):
        return details

    async def call_agent(_path, request, _answer):
        state["sent"].append(request)
        return state.get("answer", {"language": request.language, "text": "Hi [PERSON_1], the date is 1 October.",
                                    "egress": []})

    async def nothing(*_args, **_kwargs):
        return None

    async def gemini(_user_id):
        return "gemini"

    monkeypatch.setattr(dashboard, "_load_with_thread", loaded)
    monkeypatch.setattr(dashboard, "_details_for", thread_details)
    monkeypatch.setattr(dashboard, "_call_agent", call_agent)
    monkeypatch.setattr(dashboard, "save_egress", nothing)
    monkeypatch.setattr(dashboard, "audit", nothing)
    monkeypatch.setattr(dashboard, "model_for", gemini)
    return message, state


def test_a_reply_written_in_malay_goes_out_in_the_emails_language_with_details_hidden(email):
    message, state = email
    answer = asyncio.run(dashboard.translate_draft(
        str(message.id), "Hai Aisyah, tarikhnya 1 Oktober. Hubungi saya di 012-345 6789.", scope=None))
    sent = state["sent"][0]
    assert sent.language == "en"  # the email's language, not the reader's
    assert "Aisyah" not in sent.text and "[PERSON_1]" in sent.text
    assert "012-345 6789" not in sent.text
    assert answer == {"language": "en", "text": "Hi [PERSON_1], the date is 1 October."}


def test_an_unfaithful_translation_is_refused_and_nothing_changes(email, monkeypatch):
    message, _state = email

    async def refused(_path, _request, _answer):
        response = httpx.Response(422, json={"detail": {"code": "translation_unfaithful"}},
                                  request=httpx.Request("POST", "http://agent/translate"))
        raise httpx.HTTPStatusError("unfaithful", request=response.request, response=response)

    monkeypatch.setattr(dashboard, "_call_agent", refused)
    monkeypatch.setattr(dashboard.agent_client, "refusal_egress", lambda _response: [])
    with pytest.raises(dashboard.TranslationError) as error:
        asyncio.run(dashboard.translate_draft(str(message.id), "Hai, tarikhnya 1 Oktober.", scope=None))
    assert error.value.code == ErrorCode.TRANSLATION_UNFAITHFUL
