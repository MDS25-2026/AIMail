"""Nearest-rank percentile, shared by the admin console and scripts/latency.py."""

import math
from collections.abc import Sequence


def percentile[T: (int, float)](values: Sequence[T], share: float) -> T | None:
    """Always a value that was actually measured; None for no values."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(share * len(ordered)) - 1)]
