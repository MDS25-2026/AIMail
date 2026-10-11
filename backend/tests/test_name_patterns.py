"""Malaysian name shapes are found by rule where the English NER model misses them."""

import pytest

from app.core.name_patterns import find_name_patterns


@pytest.mark.parametrize("text, name", [
    ("Tell Siti Aisyah binti Ali the claim is approved.", "Siti Aisyah binti Ali"),
    ("Forward it to Razak bin Osman.", "Razak bin Osman"),
    ("Please cc Nor Hayati bt Ahmad.", "Nor Hayati bt Ahmad"),
    ("Contact AHMAD BIN ABU today.", "AHMAD BIN ABU"),
    ("The form for Kumar a/l Rajan is ready.", "Kumar a/l Rajan"),
    ("Ask Devi a/p Muthu to sign.", "Devi a/p Muthu"),
    ("Payslip for Suresh s/o Ganesan.", "Suresh s/o Ganesan"),
    ("Jimmy anak Ngau will collect it.", "Jimmy anak Ngau"),
    ("Remind Linda ak Jabu about Friday.", "Linda ak Jabu"),
    ("A note for Tengku Ahmad Zaki.", "Tengku Ahmad Zaki"),
    ("Syed Hamid called again.", "Syed Hamid"),
    ("Please thank Wan Azizah for it.", "Wan Azizah"),
    ("Muhammad Firdaus asked for leave.", "Muhammad Firdaus"),
    ("Send it to Lim Guan Eng.", "Lim Guan Eng"),
    ("Tan Mei Ling approved it.", "Tan Mei Ling"),
    ("Please reply to Encik Hafiz.", "Hafiz"),
    ("Datuk Seri Anwar will attend.", "Anwar"),
    ("Tan Sri Ahmad signed it.", "Ahmad"),
    ("R. Kumar sent the invoice.", "R. Kumar"),
    ("请转告陈美玲小姐。", "陈美玲"),
    ("王经理已经同意了。", "王"),
])
def test_a_malaysian_name_is_found(text, name):
    assert name in find_name_patterns(text)


@pytest.mark.parametrize("text", [
    "Send it to the Maybank branch in Kuala Lumpur.",
    "The refund of RM 450 is approved for Friday.",
    "Please confirm the meeting time.",
])
def test_ordinary_text_has_no_name(text):
    assert find_name_patterns(text) == []


def test_a_title_is_never_hidden_with_the_name():
    assert all(not found.startswith(("Encik", "Datuk", "Tan Sri")) for found in
               find_name_patterns("Encik Hafiz, Datuk Seri Anwar and Tan Sri Ahmad"))
