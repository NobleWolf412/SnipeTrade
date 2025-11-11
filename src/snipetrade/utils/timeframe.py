"""Utilities for timeframe parsing and manipulation."""

from __future__ import annotations


_UNIT_TO_MINUTES = {
    "m": 1,
    "h": 60,
    "d": 60 * 24,
    "w": 60 * 24 * 7,
}


def parse_tf_to_ms(timeframe: str) -> int:
    """Convert standard timeframe strings (e.g. ``1h``) into milliseconds."""

    if not timeframe:
        raise ValueError("Timeframe must be provided")

    tf = timeframe.strip().lower()
    if tf.endswith("ms"):
        value = tf[:-2]
        return int(float(value))

    unit = tf[-1]
    value = tf[:-1]

    if unit not in _UNIT_TO_MINUTES:
        raise ValueError(f"Unsupported timeframe unit: {timeframe}")

    try:
        quantity = float(value)
    except ValueError as exc:  # pragma: no cover - defensive branch
        raise ValueError(f"Invalid timeframe quantity: {timeframe}") from exc

    minutes = quantity * _UNIT_TO_MINUTES[unit]
    return int(minutes * 60 * 1000)

