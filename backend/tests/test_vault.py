"""The per-email vault and the thread map behind restorable masking.

The AI sees [PERSON_1]; the owner sees "Aisyah"; a sent reply says "Aisyah". These tests pin the
rules that make that safe: a vault opens only for its own email and owner, one person keeps one
number across a conversation, typed text is turned back into placeholders before the AI sees it,
and a placeholder with no known value can never be sent.
"""

from uuid import UUID

import pytest

from app.core import vault
from app.core.config import get_settings
from app.core.vault import ThreadMap

OWNER = UUID("aaaaaaaa-0000-4000-8000-000000000001")
KEY = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8="


@pytest.fixture(autouse=True)
def vault_key(monkeypatch, test_settings):
    monkeypatch.setenv("PII_VAULT_KEY", KEY)
    get_settings.cache_clear()


def test_a_vault_opens_for_its_own_email_and_owner():
    sealed = vault.seal_vault({"[PERSON_1]": "Aisyah"}, OWNER, "gm-1")
    assert vault.open_vault(sealed, OWNER, "gm-1") == {"[PERSON_1]": "Aisyah"}


@pytest.mark.parametrize(("owner", "gmail_id"), [(None, "gm-1"), (OWNER, "gm-2")])
def test_a_vault_copied_to_another_email_or_owner_does_not_open(owner, gmail_id):
    sealed = vault.seal_vault({"[PERSON_1]": "Aisyah"}, OWNER, "gm-1")
    with pytest.raises(vault.VaultUnavailableError):
        vault.open_vault(sealed, owner, gmail_id)


def test_without_the_key_nothing_opens(monkeypatch):
    sealed = vault.seal_vault({"[PERSON_1]": "Aisyah"}, OWNER, "gm-1")
    monkeypatch.setenv("PII_VAULT_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(vault.VaultUnavailableError):
        vault.open_vault(sealed, OWNER, "gm-1")


def _thread() -> ThreadMap:
    thread = ThreadMap()
    thread.add_message("first", {"[PERSON_1]": "Aisyah Rahman", "[PHONE_1]": "012-345 6789"},
                       "Hi, I'm [PERSON_1], call [PHONE_1]")
    thread.add_message("second", {"[PERSON_1]": "Ali", "[PERSON_2]": "aisyah  rahman"},
                       "[PERSON_1] here, cc [PERSON_2]")
    return thread


def test_one_person_keeps_one_number_across_the_conversation():
    thread = _thread()
    assert thread.renumber("first", "Hi, I'm [PERSON_1]") == "Hi, I'm [PERSON_1]"
    # Ali is new to the thread; Aisyah (different case and spacing) is the same person as before.
    assert thread.renumber("second", "[PERSON_1] here, cc [PERSON_2]") == "[PERSON_2] here, cc [PERSON_1]"


def test_numbers_already_given_never_change_as_messages_arrive():
    thread = _thread()
    before = dict(thread.values)
    thread.add_message("third", {"[PERSON_1]": "Mei Ling"}, "[PERSON_1]")
    assert {k: thread.values[k] for k in before} == before
    assert thread.values["[PERSON_3]"] == "Mei Ling"


def test_typed_text_goes_back_to_placeholders_before_the_ai_sees_it():
    thread = _thread()
    typed = "Hi AISYAH RAHMAN, Ali asked me to call 012-345 6789 or 011-2222 3333"
    safe = thread.for_model(typed)
    assert "Aisyah" not in safe.title() and "012-345 6789" not in safe and "011-2222 3333" not in safe
    assert "[PERSON_1]" in safe and "[PERSON_2]" in safe and "[PHONE_1]" in safe
    assert "[PHONE_REDACTED]" in safe  # a new number nobody had seen is masked as typed text


def test_a_value_inside_a_longer_word_is_left_alone():
    thread = ThreadMap()
    thread.add_message("m", {"[PERSON_1]": "Ali"}, "[PERSON_1]")
    assert thread.tokenise_known("Alice and Ali") == "Alice and [PERSON_1]"


def test_a_reply_is_filled_in_for_sending():
    restored, unresolved = _thread().restore("Dear [PERSON_1], we will call [PHONE_1].")
    assert restored == "Dear Aisyah Rahman, we will call 012-345 6789." and unresolved == []


def test_a_placeholder_nobody_knows_is_reported_and_never_filled_with_another_detail():
    thread = ThreadMap()
    thread.add_message("no-vault", None, "From [PERSON_1]")
    thread.add_message("with-vault", {"[PERSON_1]": "Aisyah"}, "[PERSON_1]")
    # The message without a vault got its own number, so its person can never read as Aisyah.
    assert thread.renumber("no-vault", "From [PERSON_1]") == "From [PERSON_1]"
    assert thread.renumber("with-vault", "[PERSON_1]") == "[PERSON_2]"
    restored, unresolved = thread.restore("Hi [PERSON_1] and [PERSON_2] and [PERSON_9]")
    assert unresolved == ["[PERSON_1]", "[PERSON_9]"] and "Aisyah" in restored


def test_the_owner_is_shown_only_details_that_have_a_value():
    assert _thread().details() == [
        {"placeholder": "[PERSON_1]", "value": "Aisyah Rahman", "kind": "PERSON"},
        {"placeholder": "[PHONE_1]", "value": "012-345 6789", "kind": "PHONE"},
        {"placeholder": "[PERSON_2]", "value": "Ali", "kind": "PERSON"},
    ]


def test_the_shared_placeholder_pattern_knows_every_kind_the_vault_does():
    from app.core.redaction import DETAIL_KINDS
    assert tuple(kind.value for kind in vault.DetailKind) == DETAIL_KINDS


def test_a_vault_sealed_by_the_listener_opens_here():
    import base64
    import json
    from pathlib import Path

    vector = json.loads((Path(__file__).parents[2] / "listener" / "testdata" / "vault_vector_go.json").read_text())
    sealed = base64.b64decode(vector["sealed"])
    assert vault.open_vault(sealed, UUID(vector["owner"]), vector["gmail_message_id"]) == vector["details"]


def test_a_vault_moved_to_a_new_owner_opens_for_them_and_no_longer_for_nobody():
    sealed = vault.seal_vault({"[PERSON_1]": "Aisyah"}, None, "gm-1")
    moved = vault.reseal_for_owner(sealed, "gm-1", None, OWNER)
    assert vault.open_vault(moved, OWNER, "gm-1") == {"[PERSON_1]": "Aisyah"}
    with pytest.raises(vault.VaultUnavailableError):
        vault.open_vault(moved, None, "gm-1")
