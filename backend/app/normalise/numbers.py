"""Numbers as written in business mail, in either decimal convention, parsed to one float.

Ported from the hackathon comparator (compare/normalise.py), where these rules were tested
against real shipping documents.
"""

import math
import re

THOUSANDS_GROUP_DIGITS = 3

# A number as it is written, never starting inside another one: European "21.577,00",
# "1.234.567" and "21 577,5", then "40,326", "21 577" and "40,326.5". Each alternative is
# anchored by fixed-width groups, so matching is linear on text an outside party controls.
NUMBER = (
    # Never start inside another number, including one grouped by spaces ("21 577"): a start after
    # "digit + space" made quantity matching quadratic on a run of digit groups.
    r"(?<![\d.,])(?<!\d )(?:\d{1,3}(?:\.\d{3})+,\d+|\d{1,3}(?:\.\d{3}){2,}|\d{1,3}(?: \d{3})+,\d+"
    r"|\d{1,3}(?:[ ,]\d{3})+(?:\.\d+)?|\d+(?:[.,]\d+)?)"
)
_NUMBER = re.compile(NUMBER)


def parse_number(written: str) -> float:
    """A comma is the decimal point when it comes last and either a dot comes before it or it is
    not followed by exactly three digits, so "21.577,00" and "21 577,5" read the European way
    and "40,326" as 40326. A lone "21.577" stays 21.577: it is ambiguous, read as written."""
    compact = written.replace(" ", "")
    head, comma, tail = compact.rpartition(",")
    if comma and "." not in tail and ("." in head or len(tail) != THOUSANDS_GROUP_DIGITS):
        return float(f"{head.replace('.', '').replace(',', '')}.{tail}")
    if compact.count(".") > 1:
        return float(compact.replace(".", "").replace(",", ""))
    return float(compact.replace(",", ""))


def numbers_in(text: str) -> list[float]:
    """Finite values only: a 400-digit run parses to inf, which is no figure anyone wrote."""
    return [value for value in map(parse_number, _NUMBER.findall(text)) if math.isfinite(value)]


_THOUSANDS_BY_DOTS = re.compile(r"\d{1,3}(?:\.\d{3})+")
_DECIMAL_BY_COMMA = re.compile(r"\d{1,3},\d{3}")


def _readings_of(written: str) -> set[str]:
    readings: set[str] = set()
    value = parse_number(written)
    if math.isfinite(value):
        readings.add(canonical(value))
    if _THOUSANDS_BY_DOTS.fullmatch(written):
        readings.add(canonical(float(written.replace(".", ""))))
    if _DECIMAL_BY_COMMA.fullmatch(written):
        readings.add(canonical(float(written.replace(",", "."))))
    return readings


def readings_per_figure(text: str) -> list[set[str]]:
    """Each figure in the text with every reading it can bear. "1.250" is 1.25 read the English
    way and 1250 read the Malay way; a comparison that must not misjudge either keeps both."""
    return [readings for written in _NUMBER.findall(text) if (readings := _readings_of(written))]


def figure_readings(text: str) -> set[str]:
    return set().union(*readings_per_figure(text))


def canonical(value: float) -> str:
    """One spelling per value: 18400.0 and 18400 both read "18400"; 1.50 reads "1.5"."""
    return f"{value:.10f}".rstrip("0").rstrip(".")
