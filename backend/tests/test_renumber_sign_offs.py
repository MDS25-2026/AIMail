"""scripts/renumber_sign_offs.py: old drafts onto the fixed owner and sender numbers."""

from scripts.renumber_sign_offs import renumbered

AISYAH = ("m1", {"[PERSON_1]": "Aisyah"}, "Hi I'm [PERSON_1]")


def test_the_old_sign_off_number_becomes_the_owners_fixed_one():
    assert renumbered("Hi [PERSON_1]. Regards, [PERSON_2]", [AISYAH], "Ely Tan", "") == (
        "Hi [PERSON_1]. Regards, [PERSON_900]")


def test_the_number_is_the_one_the_draft_saw_not_todays():
    # Written when the thread was one message: [PERSON_2] was the owner, though a newer message
    # has since taken that number. The script is given the thread as it was then.
    assert renumbered("Regards, [PERSON_2]", [AISYAH], "Ely Tan", "") == "Regards, [PERSON_900]"


def test_a_sender_number_after_the_owner_becomes_the_senders_fixed_one():
    draft = "Hi [PERSON_3]. Regards, [PERSON_2]"
    assert renumbered(draft, [AISYAH], "Ely Tan", "Aisyah Rahman") == "Hi [PERSON_901]. Regards, [PERSON_900]"


def test_a_name_already_in_the_thread_keeps_its_number():
    # The owner was already [PERSON_1] in the thread; that number still means them.
    thread = [("m1", {"[PERSON_1]": "Ely Tan"}, "Thanks [PERSON_1]")]
    assert renumbered("Regards, [PERSON_1]", thread, "Ely Tan", "") == "Regards, [PERSON_1]"


def test_a_draft_already_on_the_fixed_numbers_is_left_alone():
    draft = "Hi [PERSON_2]. Regards, [PERSON_900]"
    assert renumbered(draft, [AISYAH], "Ely Tan", "") == draft


def test_without_a_vault_the_names_still_get_new_numbers_and_are_renumbered():
    thread = [("m1", None, "Hi I'm [PERSON_1]")]
    assert renumbered("Regards, [PERSON_2]", thread, "Ely Tan", "") == "Regards, [PERSON_900]"
