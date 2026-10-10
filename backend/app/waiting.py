"""Which sent replies are still waiting for an answer (specs/features/todo-page.md).

A reply counts when it asks something: a question mark, or a request in English, Malay or Chinese.
Only what the user wrote is read: a reply typed in Gmail carries the other person's email quoted
underneath, and its questions would make nearly every reply count.
"""

import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

# Where the quoted email begins: "> " lines, or the header a mail client writes above it.
_QUOTE_START = re.compile(
    r"^(?:>|-{2,}\s*Original Message|From:\s|On .*wrote:\s*$|Pada .*(?:menulis|tulis):\s*$|.*写道[:：]\s*$)",
    re.IGNORECASE,
)
# A client may wrap "On Tue, 7 Oct 2026, Aisyah <a@b.c>" and "wrote:" over two lines.
_WRAPPED_HEADER_START = re.compile(r"^(?:On|Pada)\s", re.IGNORECASE)
_HEADER_END = re.compile(r"(?:wrote|menulis|tulis):\s*$|写道[:：]\s*$", re.IGNORECASE)

_QUESTION_MARKS = ("?", "？")
_REQUEST = re.compile(
    r"\b(?:please (?:confirm|advise|send|provide|reply|let me know)|let me know|could you|can you|"
    r"would you|kindly|boleh|sila|mohon|tolong|maklumkan)\b|请|能否|是否|可否|麻烦",
    re.IGNORECASE,
)


def own_text(body: str) -> str:
    """The part of a sent reply the user wrote, without the email quoted beneath it."""
    lines = body.splitlines()
    for index, line in enumerate(lines):
        if _QUOTE_START.match(line.strip()):
            return "\n".join(lines[:index])
        is_wrapped_header = (_HEADER_END.search(line.strip()) and index > 0
                             and _WRAPPED_HEADER_START.match(lines[index - 1].strip()))
        if is_wrapped_header:
            return "\n".join(lines[:index - 1])
    return body


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
