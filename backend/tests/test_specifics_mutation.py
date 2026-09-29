"""Mutation check for the unsupported-figures gate, the method the hackathon comparator used.

Every figure in a correctly grounded draft is broken one at a time, and the gate must flag
exactly that figure. Harmless rewrites (separators, the other decimal convention, trailing zeros,
a correct unit conversion) must flag nothing. A gate that passes the first set but fails the
second is noise a reviewer learns to ignore; one that fails the first is a gate that does not work.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from email_agent import unsupported_specifics

SOURCE = (
    "Invoice INV-2026-0914 totals RM 18,400.00 for 12 licences. Payment is due within 30 days. "
    "The pallet weighs 2,000 kg and ships to the depot at 25 °C."
)
GROUNDED = (
    "Thanks. Invoice INV-2026-0914 is RM 18,400.00 for 12 licences, due within 30 days. "
    "The 2,000 kg pallet ships at 25 °C."
)

BREAKS = [
    ("18,400.00", "18,500.00", "18500"),
    ("18,400.00", "1,840.00", "1840"),
    ("12 licences", "21 licences", "21"),
    ("30 days", "60 days", "60"),
    ("2,000 kg", "2,200 kg", "2200"),
    ("25 °C", "52 °C", "52"),
    ("INV-2026-0914", "INV-2026-0941", "941"),
]


def test_the_grounded_draft_is_clean():
    assert unsupported_specifics(GROUNDED, SOURCE) == []


@pytest.mark.parametrize("original, broken, flagged", BREAKS)
def test_every_broken_figure_is_flagged_alone(original, broken, flagged):
    assert unsupported_specifics(GROUNDED.replace(original, broken), SOURCE) == [flagged]


@pytest.mark.parametrize("original, harmless", [
    ("18,400.00", "18400"),
    ("18,400.00", "18.400,00"),
    ("18,400.00", "18,400"),
    ("2,000 kg", "4,409 lb"),
    ("25 °C", "77 °F"),
])
def test_a_harmless_rewrite_flags_nothing(original, harmless):
    assert unsupported_specifics(GROUNDED.replace(original, harmless), SOURCE) == []
