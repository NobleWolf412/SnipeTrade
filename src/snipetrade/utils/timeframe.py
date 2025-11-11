"""Timeframe parsing utilities."""

from __future__ import annotations

import re

__all__ = ["parse_tf_to_ms"]

# Mapping from timeframe unit to milliseconds
_UNIT_TO_MS = {
    "M": 60 * 1000,          # Minutes
    "H": 60 * 60 * 1000,     # Hours
    "D": 24 * 60 * 60 * 1000,  # Days
    "W": 7 * 24 * 60 * 60 * 1000,  # Weeks
}


def parse_tf_to_ms(tf: str) -> int:
    """Convert a timeframe string (e.g. ``15m``) to milliseconds.

    Args:
        tf: Timeframe string combining a positive integer and a unit suffix
            (``m`` for minutes, ``h`` for hours, ``d`` for days, ``w`` for weeks).

    Returns:
        The timeframe expressed in milliseconds.

    Raises:
        ValueError: If ``tf`` is empty, malformed, or uses an unsupported unit.
    """

    if not isinstance(tf, str):
        raise ValueError("Timeframe must be provided as a string")

    normalized = tf.strip().upper()
    if not normalized:
        raise ValueError("Timeframe string cannot be empty")

    match = re.fullmatch(r"(\d+)\s*([MHDW])", normalized)
    if not match:
        raise ValueError(f"Unsupported timeframe format: {tf}")

    value, unit = match.groups()
    multiplier = _UNIT_TO_MS.get(unit)
    if multiplier is None:
        raise ValueError(f"Unsupported timeframe unit: {unit}")

    amount = int(value)
    if amount <= 0:
        raise ValueError("Timeframe value must be greater than zero")

    return amount * multiplier
