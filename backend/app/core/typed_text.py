"""Fixed-format personal details in text a person typed, masked before it reaches a model.

Names stay: users type them on purpose, and masking them would fill every refined draft with
[Redacted]. The formats are the listener's (listener/main.go maskPII): both pass the shared cases in
listener/testdata/masking_vectors.json, so the two floors cannot drift apart unnoticed.
"""

import re
from enum import Enum, auto

_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
# A link keeps its scheme, host and path: query strings carry reset tokens and encoded addresses. Cut in one
# pass over the text, not with a regex, which rescanned from every "http://" (CodeQL py/polynomial-redos).
_SCHEMES = ("https://", "http://")
_LINK_END = frozenset("<>\"')]")
_QUERY_START = frozenset("?#")
# Malaysian IC: YYMMDD-PB-####, separated by dashes or spaces. Runs before phones, which would match its digits.
_IC_SEPARATED = re.compile(r"\b\d{6}[-\s]\d{2}[-\s]\d{4}\b")
# Twelve bare digits are an IC only when they start with a real date; otherwise an order or account number.
_IC_BARE = re.compile(r"\b(\d{2})(\d{2})(\d{2})\d{6}\b")
# Malaysian passports and most others: one or two letters, then seven or eight digits.
_PASSPORT = re.compile(r"\b[A-Z]{1,2}\d{7,8}\b")
_CARD = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")
_PHONE = re.compile(
    r"(?<![\w+])(?:\+\d{1,3}[\s.-]?(?:\(?\d{1,4}\)?[\s.-]?){2,4}\d{2,4}"  # international, +CC
    r"|0\d{1,2}[\s.-]?\d{3,4}[\s.-]?\d{4}"  # Malaysian local, 0XX-XXX XXXX
    r"|\(\d{3}\)[\s.-]?\d{3}[\s.-]?\d{4}"  # US, (713) 853-6161
    r"|\d{3}[\s.-]\d{3}[\s.-]\d{4}"  # US, 713-853-6161
    r"|\d{3}[.-]\d{4})(?!\w)"  # local short form, 555-0142
)


def _passes_luhn(digits: str) -> bool:
    """The card checksum, so an order or reference number of card length is not masked."""
    total = 0
    for position, char in enumerate(reversed(digits)):
        value = int(char)
        if position % 2:
            value = value * 2 - 9 if value > 4 else value * 2
        total += value
    return total % 10 == 0


def _mask_card(match: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", match.group())
    return "[CARD_REDACTED]" if _passes_luhn(digits) else match.group()


def _mask_bare_ic(match: re.Match[str]) -> str:
    month, day = int(match.group(2)), int(match.group(3))
    return "[IC_REDACTED]" if 1 <= month <= 12 and 1 <= day <= 31 else match.group()


class _Reading(Enum):
    TEXT = auto()
    LINK_START = auto()  # right after the scheme: a link needs one host character before any query
    LINK = auto()
    QUERY = auto()


def _scheme_at(text: str, at: int) -> str:
    return next((scheme for scheme in _SCHEMES if text.startswith(scheme, at)), "")


def _next(state: _Reading, char: str) -> tuple[_Reading, bool]:
    """The state after one character, and whether that character is kept."""
    if char.isspace() or char in _LINK_END:
        return _Reading.TEXT, True
    if state is _Reading.QUERY:
        return state, False
    if char in _QUERY_START:
        # "http://?x" is no link (the old pattern needed a host); a query after a host is cut.
        return (_Reading.QUERY, False) if state is _Reading.LINK else (_Reading.TEXT, True)
    return (_Reading.LINK if state is _Reading.LINK_START else state), True


def strip_link_queries(text: str) -> str:
    """Every link's query and fragment removed, in one pass: each character is read a fixed number of times."""
    kept: list[str] = []
    state, at = _Reading.TEXT, 0
    while at < len(text):
        scheme = _scheme_at(text, at) if state is _Reading.TEXT else ""
        if scheme:
            kept.append(scheme)
            state, at = _Reading.LINK_START, at + len(scheme)
            continue
        state, is_kept = _next(state, text[at])
        if is_kept:
            kept.append(text[at])
        at += 1
    return "".join(kept)


def mask_typed_text(text: str) -> str:
    """Strip link queries; replace emails, ICs, passports, card and phone numbers; leave everything else."""
    text = strip_link_queries(text)
    text = _EMAIL.sub("[EMAIL_REDACTED]", text)
    text = _IC_SEPARATED.sub("[IC_REDACTED]", text)
    text = _IC_BARE.sub(_mask_bare_ic, text)
    text = _PASSPORT.sub("[PASSPORT_REDACTED]", text)
    text = _CARD.sub(_mask_card, text)
    return _PHONE.sub("[PHONE_REDACTED]", text)
