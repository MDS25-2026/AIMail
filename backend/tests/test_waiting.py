"""Which sent replies are still waiting for an answer (specs/features/todo-page.md)."""

from datetime import datetime, timezone

import pytest

from app.waiting import asks_something, own_text, working_days_since

GMAIL_QUOTE = """Thanks, received. We'll process it this week.

On Tue, 7 Oct 2026 at 10:00, [PERSON_1] <[EMAIL_1]> wrote:
> Could you confirm the invoice amount?
> Is RM 1,250 right?"""

WRAPPED = """Noted with thanks.

On Tue, 7 Oct 2026 at 10:00, [PERSON_1]
<[EMAIL_1]> wrote:
> Can you send the PO?"""


@pytest.mark.parametrize("body", [
    GMAIL_QUOTE,
    WRAPPED,
    "Terima kasih.\n\nPada Sel, 7 Okt 2026, [PERSON_1] menulis:\n> Boleh hantar invois?",
    "谢谢，已收到。\n\n[PERSON_1] 于 2026年10月7日 写道：\n> 请确认金额？",
    "Received, thanks.\n\n-----Original Message-----\nFrom: [PERSON_1]\nCould you check?",
])
def test_a_question_in_the_quoted_email_does_not_count(body):
    assert not asks_something(body)


@pytest.mark.parametrize("body", [
    "Could you send the signed PO by Friday?",
    "Please confirm the delivery date.",
    "Boleh hantar dokumen itu esok.",
    "Sila sahkan tarikh mesyuarat.",
    "请确认付款日期。",
    "能否明天发货",
    "When can we meet？",
    f"Can you resend the PO?\n\n{GMAIL_QUOTE}",
])
def test_a_reply_that_asks_something_counts_in_all_three_languages(body):
    assert asks_something(body)


def test_only_the_users_own_lines_are_kept():
    assert own_text(GMAIL_QUOTE) == "Thanks, received. We'll process it this week.\n"


def test_working_days_skip_the_users_weekend():
    monday = datetime(2026, 10, 5, 2, tzinfo=timezone.utc)  # Mon 10:00 in Kuala Lumpur
    thursday = datetime(2026, 10, 8, 2, tzinfo=timezone.utc)
    next_monday = datetime(2026, 10, 12, 2, tzinfo=timezone.utc)
    assert working_days_since(monday, thursday, [6, 7], "Asia/Kuala_Lumpur") == 3
    assert working_days_since(monday, next_monday, [6, 7], "Asia/Kuala_Lumpur") == 5
    # Kelantan: Friday and Saturday off, Sunday a working day.
    assert working_days_since(monday, next_monday, [5, 6], "Asia/Kuala_Lumpur") == 5
    assert working_days_since(monday, datetime(2026, 10, 10, 2, tzinfo=timezone.utc),
                              [5, 6], "Asia/Kuala_Lumpur") == 3  # Tue, Wed, Thu
