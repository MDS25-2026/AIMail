from datetime import date

from app.ml.temporal import days_until, extract_deadline, priority_score
from app.ml.types import Importance

_NOW = date(2026, 7, 30)


def test_extracts_iso_slash_and_month_name_dates():
    assert extract_deadline("deadline 2026-08-15", _NOW) == date(2026, 8, 15)
    assert extract_deadline("due 8/15/2026", _NOW) == date(2026, 8, 15)
    assert extract_deadline("reply by August 15, 2026", _NOW) == date(2026, 8, 15)
    assert extract_deadline("meeting on 15 August 2026", _NOW) == date(2026, 8, 15)


def test_no_year_picks_the_next_upcoming_occurrence():
    assert extract_deadline("meeting on August 5", _NOW) == date(2026, 8, 5)
    # January already passed this year -> roll to next year
    assert extract_deadline("kickoff on January 5", _NOW) == date(2027, 1, 5)


def test_returns_earliest_upcoming_and_ignores_past_dates():
    assert extract_deadline("either August 20 or September 1", _NOW) == date(2026, 8, 20)
    assert extract_deadline("in effect since 2020-01-01", _NOW) is None


def test_no_date_and_false_positive_guards():
    assert extract_deadline("please review the policy", _NOW) is None
    # "May 2026" is a month+year, not May 20 - the day guard must reject it
    assert extract_deadline("report due May 2026", _NOW) is None


def test_days_until():
    assert days_until(date(2026, 8, 5), _NOW) == 6


def test_priority_score_combines_importance_and_recency():
    assert priority_score(Importance.HIGH, 0) == 1.0        # 0.8 + 0.20, capped
    assert priority_score(Importance.HIGH, 2) == 0.95       # 0.8 + 0.15
    assert priority_score(Importance.HIGH, 10) == 0.85      # 0.8 + 0.05
    assert priority_score(Importance.MEDIUM, None) == 0.5   # no date -> importance alone
    assert priority_score(Importance.LOW, 100) == 0.2       # far deadline -> no boost
