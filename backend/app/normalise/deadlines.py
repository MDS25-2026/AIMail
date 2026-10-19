"""The earliest deadline an email sets, for the To-do's due badges, SLA and priority
(specs/features/normalisation-v2.md). Read from English (the email's English copy when it has one), with
Malay cues and months for an email that could not be translated."""

import re
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.normalise.dates import dates_in

# A day with no time named is due at the end of the working day.
DEFAULT_DEADLINE = time(17)
NOON = time(12)
# How far after "by" the date may sit: "by 6:00 pm on Thursday 15 October" fits, the next sentence does not.
CUE_WINDOW_CHARS = 60
DAYS_IN_WEEK = 7
# "By 1 October" sent on 13 October rolls to next year: a deadline that far ahead is stale, not real.
MAX_AHEAD = timedelta(days=180)
FRIDAY = 4

_CUE = re.compile(
    r"\b(?:by|before|no later than|not later than|deadline(?: is)?|due(?: on| by)?|latest by|at the latest|"
    r"sebelum|selewat-lewatnya|paling lewat|tarikh akhir)\b",
    re.IGNORECASE,
)
_SENTENCE_END = re.compile(r"(?<!\d)\.(?!\d)|[!?\n]")
_TIME = re.compile(r"\b(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)", re.IGNORECASE)
_TIME_24H = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
_WEEKDAYS = {name: index for index, names in enumerate([
    ("monday", "isnin"), ("tuesday", "selasa"), ("wednesday", "rabu"), ("thursday", "khamis"),
    ("friday", "jumaat"), ("saturday", "sabtu"), ("sunday", "ahad")]) for name in names}
_WEEKDAY = re.compile(r"\b(" + "|".join(_WEEKDAYS) + r")\b", re.IGNORECASE)
_TODAY = re.compile(r"\b(?:today|tonight|end of (?:the )?day|eod|cob|close of business|hari ini)\b", re.IGNORECASE)
_TOMORROW = re.compile(r"\b(?:tomorrow|esok)\b", re.IGNORECASE)
_END_OF_WEEK = re.compile(r"\b(?:end of (?:the )?week|this week|minggu ini)\b", re.IGNORECASE)
_NEXT_WEEK = re.compile(r"\b(?:next week|minggu depan)\b", re.IGNORECASE)
_NOON = re.compile(r"\b(?:noon|midday|tengah hari)\b", re.IGNORECASE)


def deadline_in(text: str, sent_at: datetime, zone: str) -> datetime | None:
    """The earliest moment, after the email was sent, that it asks for something by; None when it sets none."""
    local_sent = sent_at.astimezone(ZoneInfo(zone))
    found = [moment for cue in _CUE.finditer(text)
             if (moment := _moment(_window(text, cue.end()), local_sent))
             and local_sent < moment <= local_sent + MAX_AHEAD]
    return min(found).astimezone(timezone.utc) if found else None


def _window(text: str, start: int) -> str:
    rest = text[start:start + CUE_WINDOW_CHARS]
    end = _SENTENCE_END.search(rest)
    return rest[:end.start()] if end else rest


def _moment(window: str, sent: datetime) -> datetime | None:
    day = _day(window, sent.date())
    if day is None:
        return None
    try:
        return datetime.combine(day, _time_of_day(window), tzinfo=sent.tzinfo)
    except (ValueError, OverflowError):
        return None


def _day(window: str, today: date) -> date | None:
    exact = next(iter(dates_in(window, today)), None)
    if exact is not None:
        return exact
    if _TOMORROW.search(window):
        return today + timedelta(days=1)
    if _TODAY.search(window) or _TIME.search(window) or _NOON.search(window):
        return today
    if weekday := _WEEKDAY.search(window):
        return _next(today, _WEEKDAYS[weekday.group(1).lower()])
    if _END_OF_WEEK.search(window):
        return _next(today, FRIDAY)
    if _NEXT_WEEK.search(window):
        return today + timedelta(days=DAYS_IN_WEEK - today.weekday())  # the coming Monday
    return None


def _next(today: date, weekday: int) -> date:
    """That weekday this week, or next week once it has passed; today counts."""
    return today + timedelta(days=(weekday - today.weekday()) % DAYS_IN_WEEK)


def _time_of_day(window: str) -> time:
    if _NOON.search(window):
        return NOON
    if match := _TIME.search(window):
        hour, minute, half = int(match.group(1)) % 12, int(match.group(2) or 0), match.group(3).lower()
        try:
            return time(hour + (12 if half.startswith("p") else 0), minute)
        except ValueError:
            return DEFAULT_DEADLINE
    if match := _TIME_24H.search(window):
        try:
            return time(int(match.group(1)), int(match.group(2)))
        except ValueError:
            return DEFAULT_DEADLINE
    return DEFAULT_DEADLINE
