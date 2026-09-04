"""Small shared utilities."""

from __future__ import annotations

import math


def deterministic_units(value: float) -> int:
    """Convert a model estimate to whole units using half-up rounding."""
    return max(0, math.floor(float(value) + 0.5))

