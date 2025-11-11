"""Open interest and funding regime helpers."""

from __future__ import annotations


EXTREME_THRESHOLD = 0.0005  # 5 bps


def funding_regime(funding_rate: float) -> str:
    """Classify funding into regimes."""

    try:
        rate = float(funding_rate)
    except (TypeError, ValueError):
        return "normal"

    if rate >= EXTREME_THRESHOLD:
        return "extreme_long"
    if rate <= -EXTREME_THRESHOLD:
        return "extreme_short"
    return "normal"


def oi_bias(oi_change: float) -> str:
    """Return direction of open interest change."""

    try:
        change = float(oi_change)
    except (TypeError, ValueError):
        return "flat"

    if change > 0:
        return "rising"
    if change < 0:
        return "falling"
    return "flat"
