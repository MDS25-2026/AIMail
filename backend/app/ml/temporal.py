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
from app.normalise.dates import dates_in

_IMPORTANCE_BASE: dict[Importance, float] = {
    Importance.LOW: 0.2,
    Importance.MEDIUM: 0.5,
    Importance.HIGH: 0.8,
}
# (within_days, boost) ascending; a nearer deadline lifts the score more, first match wins.
_RECENCY_BOOST: list[tuple[int, float]] = [(1, 0.20), (3, 0.15), (7, 0.10), (14, 0.05)]

# Explicit urgency markers in the text (distinct from a dated deadline). A curated lexicon rather
# than raw regex, so the signal is explainable ("priority raised because of an urgency marker").
_URGENCY_PHRASES = [
    "as soon as possible", "asap", "urgent", "urgently", "immediately",
    "right away", "time-sensitive", "time sensitive", "by eod", "by cob",
    "end of day", "quick turnaround", "expedite", "high priority",
    "top priority", "cannot wait", "can't wait", "act now", "pressing",
]
_URGENCY = re.compile(r"\b(" + "|".join(re.escape(p) for p in _URGENCY_PHRASES) + r")\b", re.IGNORECASE)
_NEGATION = re.compile(r"\b(not|no|never|isn't|aren't|won't|don't)\b", re.IGNORECASE)
_URGENCY_BOOST = 0.15
_NEGATION_WINDOW = 25  # chars before a marker to scan for a negation ("not urgent")


def has_urgency_marker(text: str) -> bool:
    """True if the text contains an urgency phrase not immediately negated (e.g. skip 'not urgent')."""
    for match in _URGENCY.finditer(text):
        before = text[max(0, match.start() - _NEGATION_WINDOW) : match.start()]
        if not _NEGATION.search(before):
            return True
    return False

def extract_deadline(text: str, now: date) -> date | None:
    """Return the earliest upcoming date mentioned in the text, or None."""
    upcoming = sorted(d for d in dates_in(text, now) if d >= now)
    return upcoming[0] if upcoming else None


def days_until(deadline: date, now: date) -> int:
    return (deadline - now).days


def priority_score(importance: Importance, days: int | None, is_urgent: bool = False) -> float:
    """Combine learned importance, days-until-deadline, and an urgency marker into a 0..1 score."""
    score = _IMPORTANCE_BASE[importance]
    if days is not None and days >= 0:
        score += next((boost for within, boost in _RECENCY_BOOST if days <= within), 0.0)
    if is_urgent:
        score += _URGENCY_BOOST
    return round(min(1.0, score), 2)
