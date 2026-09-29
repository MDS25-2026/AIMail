"""Numbers as written in business mail, in either decimal convention, parsed to one float.

Ported from the hackathon comparator (compare/normalise.py), where these rules were tested
against real shipping documents.
"""

import re

THOUSANDS_GROUP_DIGITS = 3

# A number as it is written, never starting inside another one: European "21.577,00",
# "1.234.567" and "21 577,5", then "40,326", "21 577" and "40,326.5". Each alternative is
# anchored by fixed-width groups, so matching is linear on text an outside party controls.
NUMBER = (
    r"(?<![\d.,])(?:\d{1,3}(?:\.\d{3})+,\d+|\d{1,3}(?:\.\d{3}){2,}|\d{1,3}(?: \d{3})+,\d+"
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
    return [parse_number(match) for match in _NUMBER.findall(text)]


def canonical(value: float) -> str:
    """One spelling per value: 18400.0 and 18400 both read "18400"; 1.50 reads "1.5"."""
    return f"{value:.10f}".rstrip("0").rstrip(".")
