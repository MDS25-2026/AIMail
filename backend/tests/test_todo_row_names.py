"""To-do rows show the AI's action items in the thread's numbering, so a placeholder names the right person."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from app import dashboard
from app.core import vault
from app.core.config import get_settings
from app.db.models import MaskingStatus, Message
from app.personalisation import DEFAULT_POLICY

OWNER = UUID("aaaaaaaa-0000-4000-8000-000000000002")
KEY = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8="


def _message(gmail_id: str, day: int, people: dict[str, str], **fields) -> Message:
    message = Message(id=uuid4(), user_id=OWNER, gmail_message_id=gmail_id, thread_id="t-1",
                      masking_status=MaskingStatus.COMPLETE, received_at=datetime(2026, 10, day, tzinfo=timezone.utc),
                      subject="Quote", snippet_masked="", body_masked=" ".join(people), **{"action_items": [], **fields})
    message.pii_vault = vault.seal_vault(people, OWNER, gmail_id)
    return message


@pytest.fixture
def thread(monkeypatch, test_settings):
    monkeypatch.setenv("PII_VAULT_KEY", KEY)
    get_settings.cache_clear()
    first = _message("gm-1", 1, {"[PERSON_1]": "Aisyah"})
    # In the thread's numbering Aisyah is 1, Bob 2, Charlie 3; this email alone numbers Bob 1, Charlie 2.
    second = _message("gm-2", 2, {"[PERSON_1]": "Bob", "[PERSON_2]": "Charlie"}, action_items=["Email [PERSON_2]"])
    return first, second


def test_an_action_item_names_the_person_the_ai_meant_not_whoever_has_that_number_in_this_email(thread):
    first, second = thread
    row = dashboard.thread_row(second, [first], "", DEFAULT_POLICY)
    values = {detail.placeholder: detail.value for detail in row.details}
    assert row.actionItems == ["Email [PERSON_2]"]
    assert values["[PERSON_2]"] == "Bob"
