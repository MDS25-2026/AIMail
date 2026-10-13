"""Which sent replies are still waiting for an answer (specs/features/todo-page.md).

A reply counts when it asks something: a question mark, or a request in English, Malay or Chinese.
Only what the user wrote is read: a reply typed in Gmail carries the other person's email quoted
underneath, and its questions would make nearly every reply count.
"""

import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.normalise.quotes import own_text

_QUESTION_MARKS = ("?", "？")
_REQUEST = re.compile(
    r"\b(?:please (?:confirm|advise|send|provide|reply|let me know)|let me know|could you|can you|"
    r"would you|kindly|boleh|sila|mohon|tolong|maklumkan)\b|请|能否|是否|可否|麻烦",
    re.IGNORECASE,
)


def asks_something(body: str) -> bool:
    text = own_text(body)
    return any(mark in text for mark in _QUESTION_MARKS) or _REQUEST.search(text) is not None


def working_days_since(sent_at: datetime, now: datetime, weekend_days: list[int], timezone: str) -> int:
    """Working days after the day it was sent, up to and including today, on the user's calendar."""
    zone = ZoneInfo(timezone)
    sent_day, today = sent_at.astimezone(zone).date(), now.astimezone(zone).date()
    days = (sent_day + timedelta(days=offset) for offset in range(1, (today - sent_day).days + 1))
    return sum(1 for day in days if _iso_weekday(day) not in weekend_days)


def _iso_weekday(day: date) -> int:
    return day.isoweekday()
