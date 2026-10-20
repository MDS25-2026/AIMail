"""A new email's details: typed numbers become placeholders that keep their values, and addresses are checked.

specs/features/compose.md. The database flow is in tests/test_compose_database.py.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.compose import SEND_IN_FLIGHT, checked_recipients, state_of
from app.contracts import ComposeState
from app.core.errors import DomainError, ErrorCode
from app.core.typed_text import (
    mask_typed_text,
    replace_typed_details,
    strip_link_queries,
)
from app.core.vault import OWNER_PLACEHOLDER, DetailKind, ThreadMap


def test_a_typed_phone_number_becomes_a_placeholder_that_fills_back_in():
    details = ThreadMap()
    stored = details.tokenise_typed("Call me on 012-345 6789 or mail ali@corp.com.my")
    assert stored == "Call me on [PHONE_1] or mail [EMAIL_1]"
    assert details.restore(stored) == ("Call me on 012-345 6789 or mail ali@corp.com.my", [])


def test_the_same_detail_typed_twice_keeps_one_placeholder():
    details = ThreadMap()
    assert details.tokenise_typed("012-345 6789, again 0123456789") == "[PHONE_1], again [PHONE_1]"


def test_a_stored_draft_keeps_its_numbers_when_new_details_are_added():
    details = ThreadMap.of_draft({"[PHONE_3]": "012-345 6789", "[PERSON_1]": "Harith"})
    stored = details.tokenise_typed("Harith: 012-345 6789 or 03-1234 5678")
    assert stored == "[PERSON_1]: [PHONE_3] or [PHONE_4]"


def test_links_keep_their_query_in_the_draft_but_not_for_the_model():
    details = ThreadMap()
    stored = details.tokenise_typed("Join https://meet.example.com/abc?pwd=secret today")
    assert "?pwd=secret" in stored
    assert "?pwd=secret" not in mask_typed_text(stored)


def test_the_owner_name_is_never_sealed_into_a_drafts_vault():
    details = ThreadMap()
    details.add_owner("Elyesa Tee")
    details.add_detail(DetailKind.PERSON, "Harith")
    assert OWNER_PLACEHOLDER not in details.sealable()
    assert list(details.sealable().values()) == ["Harith"]


@pytest.mark.parametrize("text", [
    "mail me at aisyah.rahman@corp.com.my", "call 012-345 6789", "her IC is 900101-14-5678",
    "passport A12345678", "card 4111 1111 1111 1111", "ref 1234 5678 9012 3456",
])
def test_the_default_replacement_is_the_masking_every_other_path_uses(text):
    assert replace_typed_details(strip_link_queries(text)) == mask_typed_text(text)


@pytest.mark.parametrize("address", [
    "harith@keris.com.my", "Harith Zulkifli <harith@keris.com.my>", '"Zulkifli, Harith" <harith@keris.com.my>',
])
def test_a_single_address_with_or_without_a_name_is_accepted(address):
    assert checked_recipients([address]) == [address]


@pytest.mark.parametrize("address", [
    "harith@keris", "not an address", "a@b.com, c@d.com", "a@b.com\r\nBcc: evil@x.com", "x" * 330 + "@b.com",
    "<harith@keris.com.my", "Harith <<harith@keris.com.my>>",
])
def test_anything_but_exactly_one_address_is_refused(address):
    with pytest.raises(DomainError) as refused:
        checked_recipients([address])
    assert refused.value.code == ErrorCode.INVALID_RECIPIENTS


def _row(**fields: object) -> SimpleNamespace:
    return SimpleNamespace(**({"sent_at": None, "send_claimed_at": None} | fields))


def test_a_draft_moves_from_sending_to_unknown_once_gmail_has_had_time_to_answer():
    now = datetime.now(timezone.utc)
    assert state_of(_row()) is ComposeState.DRAFT
    assert state_of(_row(send_claimed_at=now), now) is ComposeState.SENDING
    assert state_of(_row(send_claimed_at=now - SEND_IN_FLIGHT - timedelta(seconds=1)), now) \
        is ComposeState.OUTCOME_UNKNOWN
    assert state_of(_row(send_claimed_at=now, sent_at=now), now) is ComposeState.SENT


def test_a_placeholder_the_model_made_up_never_takes_a_new_details_number():
    details = ThreadMap.of_draft({"[PHONE_1]": "012-345 6789"}, "Call [PHONE_1] or [PHONE_2]")
    assert details.tokenise_typed("or 03-1234 5678") == "or [PHONE_3]"
    assert details.restore("[PHONE_2]")[1] == ["[PHONE_2]"]
