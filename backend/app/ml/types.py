"""Shared ML types."""

from enum import IntEnum


class Importance(IntEnum):
    """What the trained classifier predicts from email text (values, not strings)."""

    LOW = 0
    MEDIUM = 1
    HIGH = 2
