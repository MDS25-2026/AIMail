"""Deterministic temporal layer for priority (R05.1).

Extracts a deadline/meeting date from an email and combines it with the learned Importance
into a live priority score. This is rules, not ML: a date's urgency depends on the current
date, which a text classifier cannot know, and baking it into a training label would make the
label unstable. `now` is injected so the functions are pure and testable.

Scope: explicit dates only (ISO, M/D/Y, "March 15, 2026", "15 March 2026"). Natural-language
and relative dates ("next Friday", "end of week") need `dateparser` (ask-first) - a later upgrade.
"""

import re
from datetime import date

from app.ml.types import Importance

_MONTHS = {
    name[:3]: i
    for i, name in enumerate(
        [
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december",
        ],
        start=1,
    )
}

_IMPORTANCE_BASE: dict[Importance, float] = {
    Importance.LOW: 0.2,
    Importance.MEDIUM: 0.5,
    Importance.HIGH: 0.8,
}
# (within_days, boost) ascending; a nearer deadline lifts the score more, first match wins.
_RECENCY_BOOST: list[tuple[int, float]] = [(1, 0.20), (3, 0.15), (7, 0.10), (14, 0.05)]

_ISO = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_SLASH = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b")
_MONTH_DAY = re.compile(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?!\d)(?:,?\s+(\d{4}))?\b")
_DAY_MONTH = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\.?(?:,?\s+(\d{4}))?\b")


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _resolve(month: int | None, day: int, year: int | None, now: date) -> date | None:
    if month is None:
        return None
    if year is not None:
        return _safe_date(year, month, day)
    this_year = _safe_date(now.year, month, day)
    if this_year is None:
        return None
    # No year given -> the next upcoming occurrence.
    return this_year if this_year >= now else _safe_date(now.year + 1, month, day)


def _candidates(text: str, now: date):
    for match in _ISO.finditer(text):
        yield _safe_date(*(int(g) for g in match.groups()))
    for month, day, year in (m.groups() for m in _SLASH.finditer(text)):
        full_year = int(year) + 2000 if len(year) == 2 else int(year)
        yield _safe_date(full_year, int(month), int(day))
    for word, day, year in (m.groups() for m in _MONTH_DAY.finditer(text)):
        yield _resolve(_MONTHS.get(word[:3].lower()), int(day), int(year) if year else None, now)
    for day, word, year in (m.groups() for m in _DAY_MONTH.finditer(text)):
        yield _resolve(_MONTHS.get(word[:3].lower()), int(day), int(year) if year else None, now)


def extract_deadline(text: str, now: date) -> date | None:
    """Return the earliest upcoming date mentioned in the text, or None."""
    upcoming = sorted(d for d in _candidates(text, now) if d is not None and d >= now)
    return upcoming[0] if upcoming else None


def days_until(deadline: date, now: date) -> int:
    return (deadline - now).days


def priority_score(importance: Importance, days: int | None) -> float:
    """Combine learned importance with days-until-deadline into a 0..1 priority score."""
    score = _IMPORTANCE_BASE[importance]
    if days is not None and days >= 0:
        score += next((boost for within, boost in _RECENCY_BOOST if days <= within), 0.0)
    return round(min(1.0, score), 2)
