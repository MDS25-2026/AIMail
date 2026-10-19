"""The earliest deadline an email sets, for the To-do's due badges, SLA and priority
(specs/features/normalisation-v2.md). Read from English (the email's English copy when it has one), with
Malay cues and months for an email that could not be translated."""

import re
from datetime import UTC, date, datetime, time, timedelta
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
    r"sebelum|selewat-lewatnya|paling lewat|tarikh akhir)\b|"
    r"(?:截止(?:至|到|日期(?:为|是)?)?|最迟|最晚|之前)",
    re.IGNORECASE,
)
_SENTENCE_END = re.compile(r"(?<!\d)\.(?!\d)|[!?\n。！？]")
_TIME = re.compile(r"\b(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)", re.IGNORECASE)
_TIME_24H = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
_HAN_TIME = re.compile(r"(?:(上午|早上|下午|晚上)\s*)?(\d{1,2})(?:点|时|時)(?:(半)|(\d{1,2})分?)?")

_LATIN_WEEKDAYS = {name: index for index, names in enumerate([
    ("monday", "isnin"), ("tuesday", "selasa"), ("wednesday", "rabu"), ("thursday", "khamis"),
    ("friday", "jumaat"), ("saturday", "sabtu"), ("sunday", "ahad")]) for name in names}
_HAN_WEEKDAYS = {name: index for index, names in enumerate([
    ("周一", "星期一", "礼拜一"), ("周二", "星期二", "礼拜二"), ("周三", "星期三", "礼拜三"),
    ("周四", "星期四", "礼拜四"), ("周五", "星期五", "礼拜五"), ("周六", "星期六", "礼拜六"),
    ("周日", "周天", "星期日", "星期天", "礼拜天", "礼拜日")]) for name in names}
_WEEKDAYS = {**_LATIN_WEEKDAYS, **_HAN_WEEKDAYS}
_WEEKDAY = re.compile(
    r"\b(" + "|".join(_LATIN_WEEKDAYS) + r")\b|(" + "|".join(_HAN_WEEKDAYS) + r")",
    re.IGNORECASE,
)
_TODAY = re.compile(r"\b(?:today|tonight|end of (?:the )?day|eod|cob|close of business|hari ini)\b|(?:今天|今日|今晚)", re.IGNORECASE)
_TOMORROW = re.compile(r"\b(?:tomorrow|esok)\b|(?:明天|明日)", re.IGNORECASE)
_END_OF_WEEK = re.compile(r"\b(?:end of (?:the )?week|this week|minggu ini)\b|(?:本周|这周|这星期|本星期)", re.IGNORECASE)
_NEXT_WEEK = re.compile(r"\b(?:next week|minggu depan)\b|(?:下周|下个星期|下星期)", re.IGNORECASE)
_NOON = re.compile(r"\b(?:noon|midday|tengah hari)\b|(?:中午|正午)", re.IGNORECASE)


def deadline_in(text: str, sent_at: datetime, zone: str) -> datetime | None:
    """The earliest moment, after the email was sent, that it asks for something by; None when it sets none."""
    local_sent = sent_at.astimezone(ZoneInfo(zone))
    found = [moment for cue in _CUE.finditer(text)
             if (moment := _moment(_window(text, cue), local_sent))
             and local_sent < moment <= local_sent + MAX_AHEAD]
    return min(found).astimezone(UTC) if found else None


def _window(text: str, cue: re.Match[str]) -> str:
    if cue.group(0) == "之前":
        start = max(0, cue.start() - CUE_WINDOW_CHARS)
        segment = text[start:cue.start()]
        ends = list(_SENTENCE_END.finditer(segment))
        return segment[ends[-1].end():] if ends else segment
    rest = text[cue.end():cue.end() + CUE_WINDOW_CHARS]
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
    if weekday := _WEEKDAY.search(window):
        return _next(today, _WEEKDAYS[weekday.group(0).lower()])
    if _END_OF_WEEK.search(window):
        return _next(today, FRIDAY)
    if _NEXT_WEEK.search(window):
        return today + timedelta(days=DAYS_IN_WEEK - today.weekday())  # the coming Monday
    if (
        _TODAY.search(window)
        or _TIME.search(window)
        or _TIME_24H.search(window)
        or _HAN_TIME.search(window)
        or _NOON.search(window)
    ):
        return today
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
    if match := _HAN_TIME.search(window):
        period, hour, half, minute = match.group(1), int(match.group(2)), match.group(3), match.group(4)
        min_val = 30 if half else int(minute or 0)
        if period in ("下午", "晚上") and hour < 12:
            hour += 12
        elif period in ("上午", "早上") and hour == 12:
            hour = 0
        elif period is None and hour < 7:
            hour += 12
        try:
            return time(hour, min_val)
        except ValueError:
            return DEFAULT_DEADLINE
    if match := _TIME_24H.search(window):
        try:
            return time(int(match.group(1)), int(match.group(2)))
        except ValueError:
            return DEFAULT_DEADLINE
    return DEFAULT_DEADLINE
