"""Restorable masking end to end in the backend (specs/features/restorable-masking.md).

The AI only ever receives placeholders; the owner sees and sends the real details; the database
keeps placeholders. Every payload to the agent is captured and checked for the real values.
"""

import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app import dashboard
from app.core import vault
from app.core.config import get_settings
from app.core.ownership import EVERYTHING
from app.core.providers import Provider
from app.db.models import MaskingStatus, Message

OWNER = UUID("aaaaaaaa-0000-4000-8000-000000000001")
KEY = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8="
SECRETS = ("Aisyah Rahman", "012-345 6789", "Elyesa Tee")


@pytest.fixture
def mailbox(monkeypatch, test_settings):
    monkeypatch.setenv("PII_VAULT_KEY", KEY)
    get_settings.cache_clear()
    message = Message(
        id=uuid4(), user_id=OWNER, gmail_message_id="gm-1", thread_id=None,
        masking_status=MaskingStatus.COMPLETE, received_at=datetime(2026, 10, 5, tzinfo=timezone.utc),
        subject="Claim for [PERSON_1]", snippet_masked="Hi, I'm [PERSON_1]",
        body_masked="Hi, I'm [PERSON_1]. Call me on [PHONE_1].", draft_reply="Hi [PERSON_1], noted.",
        action_items=[], rag_sources=[],
    )
    message.pii_vault = vault.seal_vault({"[PERSON_1]": "Aisyah Rahman", "[PHONE_1]": "012-345 6789"}, OWNER, "gm-1")
    state = {"message": message, "payloads": [], "sent": [], "claimed": 0}

    async def load(pk, scope):
        return state["message"]

    async def load_with_thread(pk, scope):
        return state["message"], []

    async def owner_name(_owner_id):
        return "Elyesa Tee"

    async def call_agent(path, request, _answer=None):
        state["payloads"].append(json.dumps(request.model_dump(mode="json")))
        return {"draft": "Dear [PERSON_1], we will call [PHONE_1]. Regards, [PERSON_900]", "confidence": 0.9}

    async def claim(pk):
        state["claimed"] += 1
        return True

    async def send_reply(gmail_id, to, subject, body, *, owner_id):
        state["sent"].append(body)
        return _Sent()

    async def nothing(*_args, **_kwargs):
        return None

    async def can_send(_user_id):
        return True

    async def no_chunks(*_args, **_kwargs):
        return []

    async def no_style(_user_id):
        return {}

    async def no_egress(_message_id):
        return []

    async def gemini(_user_id):
        return Provider.GEMINI

    async def no_schedules(_message_ids):
        return {}

    for name, value in (("_load", load), ("_load_with_thread", load_with_thread), ("_owner_name", owner_name),
                        ("retrieve", no_chunks), ("_mark_read", nothing),
                        ("_call_agent", call_agent), ("_claim_send", claim), ("send_reply", send_reply),
                        ("audit", nothing), ("_update_unsent", _true), ("_style_fields", no_style),
                        ("is_learning", _false), ("provider_for", gemini), ("egress_for", no_egress),
                        ("save_egress", nothing), ("request_draft", nothing), ("release_drafting", nothing),
                        ("suggested_template_id", nothing), ("states_for", no_schedules),
                        ("cancel_pending", _false)):
        monkeypatch.setattr(dashboard, name, value)
    monkeypatch.setattr(dashboard.connections, "can_send", can_send)
    return state


async def _true(*_args, **_kwargs):
    return True


async def _false(*_args, **_kwargs):
    return False


class _Sent:
    gmail_id = "g-sent-1"
    message_id = "<m>"
    thread_id = "t1"


class _Session:
    def __init__(self, message):
        self.message = message

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    async def get(self, _model, _pk):
        return self.message

    def add(self, row):
        self.added = [*getattr(self, "added", []), row]

    async def execute(self, statement):
        self.executed = [*getattr(self, "executed", []), statement]

    async def commit(self):
        return None


def _no_secret_in(payloads):
    for payload in payloads:
        for secret in SECRETS:
            assert secret not in payload, f"{secret!r} reached the agent"


def test_the_owner_sees_the_real_details_behind_every_placeholder(mailbox):
    email = asyncio.run(dashboard.email_detail(str(mailbox["message"].id), scope=EVERYTHING))
    assert email.body == "Hi, I'm [PERSON_1]. Call me on [PHONE_1]."
    shown = {detail.placeholder: detail.value for detail in email.details}
    assert shown["[PERSON_1]"] == "Aisyah Rahman" and shown["[PHONE_1]"] == "012-345 6789"


def test_a_refine_with_real_names_typed_in_sends_the_agent_placeholders_only(mailbox):
    asyncio.run(dashboard.refine_email(str(mailbox["message"].id), "Tell Aisyah Rahman we'll ring 012-345 6789",
                                       "Hi Aisyah Rahman, noted. Elyesa Tee", scope=EVERYTHING))
    payload = json.loads(mailbox["payloads"][0])
    assert "[PERSON_1]" in payload["draft"] and "[PHONE_1]" in payload["instruction"]
    # The owner's own name is a placeholder too, used for the sign-off.
    assert payload["sign_off"] == "[PERSON_900]" and "[PERSON_900]" in payload["draft"]
    _no_secret_in(mailbox["payloads"])


def test_a_regenerated_draft_is_asked_for_with_placeholders_only(mailbox):
    asyncio.run(dashboard.regenerate_email(str(mailbox["message"].id), scope=EVERYTHING))
    _no_secret_in(mailbox["payloads"])
    assert json.loads(mailbox["payloads"][0])["sign_off"] == "[PERSON_900]"


def test_an_approved_reply_goes_out_with_the_real_details_and_is_stored_with_placeholders(mailbox, monkeypatch):
    message = mailbox["message"]
    monkeypatch.setattr(dashboard, "get_sessionmaker", lambda: lambda: _Session(message))
    asyncio.run(dashboard.approve_and_send(str(message.id), "Dear [PERSON_1], we will call 012-345 6789.",
                                           scope=EVERYTHING))
    assert mailbox["sent"] == ["Dear Aisyah Rahman, we will call 012-345 6789."]
    assert message.draft_reply == "Dear [PERSON_1], we will call [PHONE_1]."


def test_a_sent_reply_is_kept_for_the_waiting_list_with_placeholders_only(mailbox, monkeypatch):
    message = mailbox["message"]
    session = _Session(message)
    monkeypatch.setattr(dashboard, "get_sessionmaker", lambda: lambda: session)
    asyncio.run(dashboard.approve_and_send(str(message.id), "Dear [PERSON_1], could you call 012-345 6789?",
                                           scope=EVERYTHING, remind=True))
    inserted = [s.compile().params for s in session.executed if "sent_message" in str(s)]
    assert len(inserted) == 1
    assert inserted[0]["body_masked"] == "Dear [PERSON_1], could you call [PHONE_1]?"
    assert inserted[0]["remind"] is True and inserted[0]["message_id"] == message.id
    _no_secret_in([inserted[0]["body_masked"]])


def test_a_placeholder_nobody_can_fill_stops_the_send_before_anything_is_claimed(mailbox):
    with pytest.raises(dashboard.SendRejectedError) as caught:
        asyncio.run(dashboard.approve_and_send(str(mailbox["message"].id), "Dear [PERSON_7]", scope=EVERYTHING))
    assert (caught.value.code, caught.value.status_code) == (dashboard.ErrorCode.UNRESOLVED_PLACEHOLDERS, 422)
    assert mailbox["claimed"] == 0 and mailbox["sent"] == []


def test_without_the_key_the_owner_sees_placeholders_and_cannot_send_them(mailbox, monkeypatch):
    monkeypatch.setenv("PII_VAULT_KEY", "")
    get_settings.cache_clear()
    email = asyncio.run(dashboard.email_detail(str(mailbox["message"].id), scope=EVERYTHING))
    assert email.details == [detail for detail in email.details if detail.value == "Elyesa Tee"]
    with pytest.raises(dashboard.SendRejectedError):
        asyncio.run(dashboard.approve_and_send(str(mailbox["message"].id), "Hi [PERSON_1]", scope=EVERYTHING))


def test_an_email_from_before_restorable_masking_behaves_as_it_always_did(mailbox, monkeypatch):
    old = mailbox["message"]
    old.pii_vault = None
    old.body_masked = "Hi, I'm [Redacted]"
    monkeypatch.setattr(dashboard, "get_sessionmaker", lambda: lambda: _Session(old))
    with pytest.raises(dashboard.SendRejectedError) as caught:
        asyncio.run(dashboard.approve_and_send(str(old.id), "Hi [Redacted]", scope=EVERYTHING))
    assert caught.value.code == dashboard.ErrorCode.REDACTION_MARKERS
    asyncio.run(dashboard.approve_and_send(str(old.id), "Hi Aisyah, thanks.", scope=EVERYTHING))
    assert mailbox["sent"] == ["Hi Aisyah, thanks."]


def test_an_inbox_row_shows_its_own_details(mailbox):
    row = dashboard._to_email(mailbox["message"], details=dashboard._own_details(mailbox["message"]))
    assert row.subject == "Claim for [PERSON_1]"
    assert {d.placeholder: d.value for d in row.details}["[PERSON_1]"] == "Aisyah Rahman"


def _template(body: str) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), user_id=OWNER, body=body, language="en")


def test_a_template_fills_the_sender_and_owner_as_placeholders(mailbox):
    mailbox["message"].from_addr = "Aisyah Rahman <aisyah@example.com>"
    filled = asyncio.run(dashboard.fill_template(
        str(mailbox["message"].id), _template("Hi {{name}}, regards {{my name}}. {{meeting link}}"),
        scope=EVERYTHING))
    # The sender and the owner have fixed numbers, whoever else the thread names.
    assert filled == "Hi [PERSON_901], regards [PERSON_900]. {{meeting link}}"
    assert mailbox["payloads"] == []  # filling asks no model


def test_a_template_adapted_by_the_agent_reaches_it_with_placeholders_only(mailbox):
    mailbox["message"].from_addr = "Aisyah Rahman <aisyah@example.com>"
    body = "Hi {{name}}, I'll ring Aisyah Rahman on 012-345 6789. {{my name}}"
    asyncio.run(dashboard.adapt_template(str(mailbox["message"].id), _template(body), scope=EVERYTHING))
    payload = json.loads(mailbox["payloads"][0])
    assert payload["draft"].startswith("Hi [PERSON_901]") and "[PHONE_1]" in payload["draft"]
    _no_secret_in(mailbox["payloads"])


def test_the_suggestion_uses_the_viewers_templates_even_on_an_unowned_email(mailbox, monkeypatch):
    asked = []

    async def suggested(user_id, _text):
        asked.append(user_id)
        return "tpl-1"

    monkeypatch.setattr(dashboard, "suggested_template_id", suggested)
    mailbox["message"].user_id = None  # the original mailbox's rows have no owner yet
    email = asyncio.run(dashboard.email_detail(str(mailbox["message"].id), scope=EVERYTHING, viewer_id=OWNER))
    assert email.suggestedTemplateId == "tpl-1" and asked == [OWNER]
