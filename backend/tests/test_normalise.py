"""The normalisation layer: one reading of numbers, quantities and dates."""

from datetime import date

import pytest

from app.normalise.dates import dates_in, slash_date
from app.normalise.numbers import canonical, numbers_in, parse_number
from app.normalise.quantities import converted_figures, quantities_in


@pytest.mark.parametrize("written, value", [
    ("21.577,00", 21577.0), ("21 577,5", 21577.5), ("40,326", 40326.0), ("18,400.00", 18400.0),
    ("1.234.567", 1234567.0), ("21.577", 21.577), ("7", 7.0),
])
def test_both_decimal_conventions_parse_to_one_value(written, value):
    assert parse_number(written) == value


def test_one_spelling_per_value():
    assert canonical(18400.0) == "18400" and canonical(1.50) == "1.5"


@pytest.mark.parametrize("text, metric, imperial", [
    ("2,000 lb", (907.0, "kg"), (2000.0, "lb")),
    ("30 °C", (30.0, "°C"), (86.0, "°F")),
    ("5 km", (5.0, "km"), (3.11, "mi")),
    ("0.4 km", (0.4, "km"), (1312.0, "ft")),
    ("3.5 litres", (3.5, "L"), (0.925, "gal")),
    ("1.234.567 kg", (1234567.0, "kg"), (2721754.0, "lb")),
])
def test_quantities_convert_both_ways_and_echo_the_written_side_exactly(text, metric, imperial):
    (found,) = quantities_in(text)
    assert (found.metric.value, found.metric.unit) == metric
    assert (found.imperial.value, found.imperial.unit) == imperial


@pytest.mark.parametrize("text", [
    "our 5G network", "back in 2 days", "fined 50 pounds", "a RM5m budget", "raised $2m",
    "ticket 12G", "Room 5m",
])
def test_things_that_are_not_quantities_are_left_alone(text):
    assert quantities_in(text) == []


def test_a_correct_conversion_of_a_source_figure_is_supported():
    assert converted_figures("That is 4,409 lb.", "Gross weight 2,000 kg") == {"4409"}


def test_a_wrong_conversion_is_not():
    assert converted_figures("That is 4,000 lb.", "Gross weight 2,000 kg") == set()


def test_the_same_unit_needs_the_same_figure():
    assert converted_figures("That is 2,010 kg.", "Gross weight 2,000 kg") == set()


NOW = date(2026, 9, 29)


@pytest.mark.parametrize("text, expected", [
    ("due 30/09/2026", date(2026, 9, 30)),
    ("due 8/15/2026", date(2026, 8, 15)),
    ("due 2026-10-05", date(2026, 10, 5)),
    ("due 5 October 2026", date(2026, 10, 5)),
    ("due Oct 5, 2026", date(2026, 10, 5)),
])
def test_dates_resolve_regardless_of_how_they_are_written(text, expected):
    assert list(dates_in(text, NOW)) == [expected]


def test_an_ambiguous_slash_date_follows_the_configured_order(monkeypatch):
    monkeypatch.setenv("DATE_ORDER", "DMY")
    assert slash_date(5, 9, 2026) == date(2026, 9, 5)
    monkeypatch.setenv("DATE_ORDER", "MDY")
    assert slash_date(5, 9, 2026) == date(2026, 5, 9)


def test_an_unknown_date_order_falls_back_to_day_first(monkeypatch):
    monkeypatch.setenv("DATE_ORDER", "YMD?")
    assert slash_date(5, 9, 2026) == date(2026, 9, 5)


def test_an_absurdly_long_number_is_skipped_not_a_crash():
    """One hostile email must not 500 the whole inbox list, which builds every row."""
    huge = "1" + "0" * 400
    assert quantities_in(f"{huge} kg") == []
    assert numbers_in(huge) == []
