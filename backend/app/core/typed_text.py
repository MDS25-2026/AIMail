"""Fixed-format personal details in text a person typed, masked before it reaches a model.

Names stay: users type them on purpose, and masking them would fill every refined draft with
[Redacted]. The tokens match the listener's (listener/main.go), so the send check catches any that
survive into a reply.
"""

import re

_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
# Malaysian IC: YYMMDD-PB-####, dashes optional. Runs before phones, which would match its digits.
_IC = re.compile(r"\b\d{6}-?\d{2}-?\d{4}\b")
# Malaysian passports and most others: one or two letters, then seven or eight digits.
_PASSPORT = re.compile(r"\b[A-Z]{1,2}\d{7,8}\b")
_CARD = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")
_PHONE = re.compile(
    r"(?<![\w+])(?:\+\d{1,3}[\s.-]?(?:\(?\d{1,4}\)?[\s.-]?){2,4}\d{2,4}"  # international, +CC
    r"|0\d{1,2}[\s.-]?\d{3,4}[\s.-]?\d{4})(?!\w)"  # Malaysian local, 0XX-XXX XXXX
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


def mask_typed_text(text: str) -> str:
    """Replace emails, ICs, passports, card numbers and phone numbers; leave everything else."""
    text = _EMAIL.sub("[EMAIL_REDACTED]", text)
    text = _IC.sub("[IC_REDACTED]", text)
    text = _PASSPORT.sub("[PASSPORT_REDACTED]", text)
    text = _CARD.sub(_mask_card, text)
    return _PHONE.sub("[PHONE_REDACTED]", text)
