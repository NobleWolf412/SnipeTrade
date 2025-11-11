"""Utility helpers for timeframe handling."""

from __future__ import annotations

import re
from typing import Iterable, List


_TIMEFRAME_PATTERN = re.compile(r"^(\d+)([mhdw])$", re.IGNORECASE)
_UNIT_TO_SECONDS = {
    "m": 60,
    "h": 60 * 60,
    "d": 60 * 60 * 24,
    "w": 60 * 60 * 24 * 7,
}


def timeframe_to_seconds(timeframe: str) -> int:
    """Convert a timeframe string to seconds.

    Args:
        timeframe: A CCXT-style timeframe such as ``"15m"`` or ``"1h"``.

    Returns:
        The timeframe converted to seconds.

    Raises:
        ValueError: If ``timeframe`` is not in a recognised format.
    """

    if not timeframe:
        raise ValueError("timeframe must be a non-empty string")

    match = _TIMEFRAME_PATTERN.match(timeframe.strip())
    if not match:
        raise ValueError(f"Unsupported timeframe format: {timeframe}")

    value = int(match.group(1))
    unit = match.group(2).lower()
    return value * _UNIT_TO_SECONDS[unit]


def normalize_timeframes(timeframes: Iterable[str]) -> List[str]:
    """Normalise and sort timeframe strings.

    The function ensures that duplicate entries are removed and that the
    resulting list is ordered from the lowest to the highest timeframe.
    """

    seen = set()
    ordered: List[str] = []

    for timeframe in timeframes:
        if not timeframe:
            continue
        normalized = timeframe.strip().lower()
        if normalized not in seen:
            seen.add(normalized)
            ordered.append(normalized)

    ordered.sort(key=timeframe_to_seconds)
    return ordered


__all__ = ["normalize_timeframes", "timeframe_to_seconds"]

