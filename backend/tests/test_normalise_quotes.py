"""One quote splitter for the backend, matching the listener's and the dashboard's."""

import pytest

from app.normalise.quotes import own_text


@pytest.mark.parametrize(("body", "own"), [
    ("Noted.\n\nFrom: [PERSON_1]\nSent: Monday, 6 October 2026\nSubject: Quote", "Noted.\n"),
    ("Noted.\nSent: Monday, 6 October 2026", "Noted."),
    ("Baik.\nPada Isnin, [PERSON_1] menulis:\n> Boleh?", "Baik."),
    ("好的。\n[PERSON_1] 写道：\n> 可以吗？", "好的。"),
    ("Yes.\nOn Tue, 7 Oct 2026, [PERSON_1] <[EMAIL_1]>\nwrote:\n> Ready?", "Yes."),
    ("No quote here.", "No quote here."),
])
def test_only_what_the_sender_wrote_is_kept(body, own):
    assert own_text(body) == own
