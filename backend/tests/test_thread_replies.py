"""The owner's own replies appear in the thread, under the email they answered.

A reply sent from AIMail is stored on the email it answered (draft_reply + sent_at), not as a row of
its own. When the other person writes back, the thread shows both sides, and the model drafting the
next reply knows what was already said.
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app import attachment_notes
from app.core.vault import ThreadMap
from app.dashboard import _thread_view, _to_email, thread_context
from app.db.models import AuditLog, Message, SentMessage

T0 = datetime(2026, 10, 5, 7, 0, tzinfo=timezone.utc)


def _message(minutes: int, body: str, **fields) -> Message:
    return Message(id=uuid4(), received_at=T0 + timedelta(minutes=minutes), body_masked=body,
                   snippet_masked=body, from_addr="Aisyah <a@example.com>", **fields)


def test_the_owners_reply_is_listed_right_under_the_email_it_answered():
    original = _message(0, "Can I claim the course fee?", sent_at=T0 + timedelta(minutes=5),
                        draft_reply="Hi Aisyah, yes, within 14 days.")
    later = _message(10, "Thanks, and the travel costs?")
    view = _thread_view([original, later], ThreadMap())
    assert [(m.isOwnReply, m.snippet) for m in view] == [
        (False, "Can I claim the course fee?"),
        (True, "Hi Aisyah, yes, within 14 days."),
        (False, "Thanks, and the travel costs?"),
    ]


def test_an_unsent_draft_is_not_shown_as_a_reply():
    view = _thread_view([_message(0, "Hello", draft_reply="Not sent yet")], ThreadMap())
    assert [m.isOwnReply for m in view] == [False]


def test_the_model_sees_what_the_owner_already_replied_with_typed_details_masked():
    original = _message(0, "Can I claim?", sent_at=T0 + timedelta(minutes=5),
                        draft_reply="Yes. Call me on 012-345 6789.")
    current = _message(10, "And travel?")
    context = thread_context(current, [original])
    assert "Your reply to earlier message 1:" in context
    assert "012-345 6789" not in context and "[PHONE_REDACTED]" in context
    assert "Aisyah" not in context, "the sender's name must never enter a model payload"


def test_each_message_in_the_conversation_carries_its_full_body_and_time():
    original = _message(0, "Can I claim the course fee?", sent_at=T0 + timedelta(minutes=5),
                        draft_reply="Hi [PERSON_1], yes.")
    view = _thread_view([original], ThreadMap())
    assert view[0].body == "Can I claim the course fee?" and view[0].timestamp == T0.isoformat()
    assert view[1].isOwnReply and view[1].body == "Hi [PERSON_1], yes."
    assert view[1].timestamp == (T0 + timedelta(minutes=5)).isoformat()


# ---------- Replies sent from Gmail itself (specs/features/readable-emails.md) ----------

def _gmail_reply(minutes: int, body: str) -> SentMessage:
    return SentMessage(id=uuid4(), sent_at=T0 + timedelta(minutes=minutes), body_masked=body, thread_id="t1")


def test_a_reply_sent_from_gmail_appears_where_it_falls_in_time():
    view = _thread_view([_message(0, "Can I claim it?"), _message(20, "And the hotel?")], ThreadMap(),
                        [_gmail_reply(10, "Yes, within 14 days.")])
    assert [(m.isOwnReply, m.snippet) for m in view] == [
        (False, "Can I claim it?"), (True, "Yes, within 14 days."), (False, "And the hotel?")]


def test_a_gmail_replys_hidden_name_never_takes_another_persons_name():
    message = _message(0, "Hi, I'm [PERSON_1].", subject="Claim", gmail_message_id="gm-1")
    details = ThreadMap()
    details.add_message(str(message.id), {"[PERSON_1]": "Aisyah"}, "Hi, I'm [PERSON_1].")
    # In its own numbering, [PERSON_1] is someone else entirely; it has no stored value.
    email = _to_email(message, details=details, sent=[_gmail_reply(5, "Thanks [PERSON_1]")])
    reply = next(entry for entry in email.threadContext if entry.isOwnReply)
    values = {detail.placeholder: detail.value for detail in email.details}
    assert "[PERSON_1]" not in reply.body
    assert values == {"[PERSON_1]": "Aisyah"}


# ---------- An attachment the listener could not read ----------

class _Rows:
    def __init__(self, rows):
        self.rows = rows

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    async def scalars(self, _statement):
        return type("Result", (), {"all": lambda _self: self.rows})()


def _audit(action: str, fields: dict, success: bool = False) -> AuditLog:
    return AuditLog(action=action, detail=json.dumps(fields), success=success)


@pytest.mark.parametrize(("rows", "expected"), [
    ([_audit("ocr_attachment", {"gmail_message_id": "gm-1", "stage": "read_locally"})], True),
    ([_audit("drop_attachment_text", {"gmail_message_id": "gm-1"})], False),
    ([_audit("ocr_attachment", {"gmail_message_id": "gm-10", "stage": "read_locally"})], False),
    ([], False),
])
def test_an_email_says_when_an_attachment_could_not_be_read(monkeypatch, rows, expected):
    monkeypatch.setattr(attachment_notes, "get_sessionmaker", lambda: lambda: _Rows(rows))
    message = Message(id=uuid4(), gmail_message_id="gm-1")
    assert asyncio.run(attachment_notes.has_unread_attachment(message)) is expected
