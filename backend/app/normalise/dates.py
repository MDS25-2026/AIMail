"""Dates as written in mail, resolved to calendar dates.

Moved from app/ml/temporal.py, which now imports it, so there is one reading of a date.
"""

import os
import re
from collections.abc import Iterator
from datetime import date
from enum import StrEnum


class DateOrder(StrEnum):
    DAY_FIRST = "DMY"
    MONTH_FIRST = "MDY"


# Malaysia, the UK and most of the world write day first; the US writes month first.
DEFAULT_DATE_ORDER = DateOrder.DAY_FIRST
MONTHS_IN_YEAR = 12
TWO_DIGIT_YEAR_BASE = 2000

MONTHS = {
    name[:3]: i
    for i, name in enumerate(
        [
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december",
        ],
        start=1,
    )
}

_ISO = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_SLASH = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b")
_MONTH_DAY = re.compile(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?!\d)(?:,?\s+(\d{4}))?\b")
_DAY_MONTH = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\.?(?:,?\s+(\d{4}))?\b")


def date_order() -> DateOrder:
    """From DATE_ORDER; anything unrecognised falls back to day first rather than failing."""
    raw = os.getenv("DATE_ORDER", "").upper()
    return DateOrder(raw) if raw in DateOrder._value2member_map_ else DEFAULT_DATE_ORDER


def safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _resolve(month: int | None, day: int, year: int | None, now: date) -> date | None:
    if month is None:
        return None
    if year is not None:
        return safe_date(year, month, day)
    this_year = safe_date(now.year, month, day)
    if this_year is None:
        return None
    # No year given -> the next upcoming occurrence.
    return this_year if this_year >= now else safe_date(now.year + 1, month, day)


def slash_date(first: int, second: int, year: int) -> date | None:
    """A side over 12 can only be the day, which settles the order; otherwise DATE_ORDER does."""
    if first > MONTHS_IN_YEAR:
        return safe_date(year, second, first)
    if second > MONTHS_IN_YEAR:
        return safe_date(year, first, second)
    if date_order() == DateOrder.DAY_FIRST:
        return safe_date(year, second, first)
    return safe_date(year, first, second)


def dates_in(text: str, now: date) -> Iterator[date]:
    """Every date the text names. Unparseable candidates are skipped, never guessed."""
    candidates: list[date | None] = []
    candidates += [safe_date(*(int(g) for g in m.groups())) for m in _ISO.finditer(text)]
    for first, second, year in (m.groups() for m in _SLASH.finditer(text)):
        full_year = int(year) + TWO_DIGIT_YEAR_BASE if len(year) == 2 else int(year)
        candidates.append(slash_date(int(first), int(second), full_year))
    for word, day, year in (m.groups() for m in _MONTH_DAY.finditer(text)):
        candidates.append(_resolve(MONTHS.get(word[:3].lower()), int(day),
                                   int(year) if year else None, now))
    for day, word, year in (m.groups() for m in _DAY_MONTH.finditer(text)):
        candidates.append(_resolve(MONTHS.get(word[:3].lower()), int(day),
                                   int(year) if year else None, now))
    return (found for found in candidates if found is not None)
