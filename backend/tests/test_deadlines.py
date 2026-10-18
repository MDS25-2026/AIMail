"""The earliest deadline an email sets (specs/features/normalisation-v2.md)."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.normalise.dates import dates_in
from app.normalise.deadlines import deadline_in

KL = "Asia/Kuala_Lumpur"
# Tuesday 13 October 2026, 10:00 in Kuala Lumpur.
SENT = datetime(2026, 10, 13, 10, 0, tzinfo=ZoneInfo(KL))


def local(text: str) -> datetime | None:
    found = deadline_in(text, SENT, KL)
    return found.astimezone(ZoneInfo(KL)) if found else None


def kl(*parts: int) -> datetime:
    return datetime(*parts, tzinfo=ZoneInfo(KL))


def test_the_vendor_review_email_is_due_at_noon_tomorrow_its_earliest_ask():
    text = ("Please confirm whether you can attend the new slot by 12:00 noon tomorrow, Wednesday 14 October. "
            "Please send me the updated cost comparison slides by 6:00 pm on Thursday 15 October.")
    assert local(text) == kl(2026, 10, 14, 12, 0)


@pytest.mark.parametrize(("text", "due"), [
    ("Please reply by Friday.", kl(2026, 10, 16, 17, 0)),
    ("Kindly send it before 5pm today.", kl(2026, 10, 13, 17, 0)),
    ("We need this by end of week.", kl(2026, 10, 16, 17, 0)),
    ("Payment is due on 30 October 2026.", kl(2026, 10, 30, 17, 0)),
    ("Sila hantar sebelum Khamis.", kl(2026, 10, 15, 17, 0)),
    ("Sila sahkan selewat-lewatnya 20 Oktober.", kl(2026, 10, 20, 17, 0)),
    ("No later than 2026-10-21 18:30.", kl(2026, 10, 21, 18, 30)),
])
def test_deadlines_in_english_and_malay(text, due):
    assert local(text) == due


@pytest.mark.parametrize("text", [
    "The meeting was on 1 October.",            # a date, but nothing asked by it
    "Please send it by 1 October.",            # already past when sent
    "Thanks for your help last week.",
])
def test_no_deadline_when_none_is_set(text):
    assert local(text) is None


def test_chinese_and_malay_month_names_are_read_as_dates():
    today = datetime(2026, 10, 13, tzinfo=timezone.utc).date()
    assert [d.isoformat() for d in dates_in("请在10月15日前回复", today)] == ["2026-10-15"]
    assert [d.isoformat() for d in dates_in("24 Ogos 2026", today)] == ["2026-08-24"]
