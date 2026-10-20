"""Fixed-format personal details in text a person typed, masked before it reaches a model.

Names are not handled here: app/core/typed_names.py hides them with placeholders for one request and
puts them back after, so this stays a fast, synchronous floor. The formats are the listener's (listener/main.go maskPII): both pass the shared cases in
listener/testdata/masking_vectors.json, so the two floors cannot drift apart unnoticed.
"""

import re
from collections.abc import Callable
from enum import Enum, StrEnum, auto

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


class TypedDetail(StrEnum):
    """The fixed formats found here, named as the vault's detail kinds (app/core/vault.py DetailKind)."""

    EMAIL = "EMAIL"
    IC = "IC"
    PASSPORT = "PASSPORT"
    CARD = "CARD"
    PHONE = "PHONE"


# What a found detail becomes: a marker for good by default, a restorable placeholder for Compose.
Replace = Callable[[TypedDetail, str], str]


def redacted(kind: TypedDetail, _value: str) -> str:
    return f"[{kind}_REDACTED]"


def _mask_card(match: re.Match[str], replace: Replace) -> str:
    digits = re.sub(r"\D", "", match.group())
    return replace(TypedDetail.CARD, match.group()) if _passes_luhn(digits) else match.group()


def _mask_bare_ic(match: re.Match[str], replace: Replace) -> str:
    month, day = int(match.group(2)), int(match.group(3))
    return replace(TypedDetail.IC, match.group()) if 1 <= month <= 12 and 1 <= day <= 31 else match.group()


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


_BUSINESS_PREFIXES = frozenset({
    "billing", "support", "help", "info", "contact", "sales", "inquiries",
    "enquiries", "admin", "service", "customerservice", "legal", "compliance",
    "privacy", "security", "press", "media", "feedback", "team", "office",
})


def _mask_email_match(match: re.Match[str], *, preserve_business: bool = False, replace: Replace = redacted) -> str:
    addr = match.group().lower()
    if preserve_business:
        prefix = addr.split("@")[0].split(".")[0].split("+")[0]
        if prefix in _BUSINESS_PREFIXES:
            return match.group()
    return replace(TypedDetail.EMAIL, match.group())


_HAN = re.compile(r"[\u4e00-\u9fff]")


def whole_words(value: str) -> str:
    """A pattern for the value as whole words, any run of spaces between them. Chinese has no spaces
    between words, so a value written in characters is matched wherever it stands."""
    words = r"\s+".join(map(re.escape, value.split()))
    return words if _HAN.search(value) else rf"(?<!\w){words}(?!\w)"


def replace_typed_details(text: str, *, preserve_business_emails: bool = False, replace: Replace = redacted) -> str:
    """Every email, IC, passport, card and phone number passed through `replace`; links left whole."""
    text = _EMAIL.sub(lambda m: _mask_email_match(m, preserve_business=preserve_business_emails, replace=replace), text)
    text = _IC_SEPARATED.sub(lambda m: replace(TypedDetail.IC, m.group()), text)
    text = _IC_BARE.sub(lambda m: _mask_bare_ic(m, replace), text)
    text = _PASSPORT.sub(lambda m: replace(TypedDetail.PASSPORT, m.group()), text)
    text = _CARD.sub(lambda m: _mask_card(m, replace), text)
    return _PHONE.sub(lambda m: replace(TypedDetail.PHONE, m.group()), text)


def mask_typed_text(text: str, *, preserve_business_emails: bool = False) -> str:
    """Strip link queries; replace emails, ICs, passports, card and phone numbers; leave everything else."""
    return replace_typed_details(strip_link_queries(text), preserve_business_emails=preserve_business_emails)
