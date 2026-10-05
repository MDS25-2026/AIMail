"""The owner's own replies appear in the thread, under the email they answered.

A reply sent from AIMail is stored on the email it answered (draft_reply + sent_at), not as a row of
its own. When the other person writes back, the thread shows both sides, and the model drafting the
next reply knows what was already said.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.vault import ThreadMap
from app.dashboard import _thread_view, thread_context
from app.db.models import Message

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
