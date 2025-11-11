"""Utility helpers for working with exchange timeframes and symbols."""

from __future__ import annotations

from typing import Dict

# Mapping of CCXT style timeframes to their duration in milliseconds.
_TIMEFRAME_TO_MS: Dict[str, int] = {
    "1m": 60_000,
    "3m": 3 * 60_000,
    "5m": 5 * 60_000,
    "15m": 15 * 60_000,
    "30m": 30 * 60_000,
    "1h": 60 * 60_000,
    "2h": 2 * 60 * 60_000,
    "4h": 4 * 60 * 60_000,
    "6h": 6 * 60 * 60_000,
    "12h": 12 * 60 * 60_000,
    "1d": 24 * 60 * 60_000,
    "3d": 3 * 24 * 60 * 60_000,
    "1w": 7 * 24 * 60 * 60_000,
    "1M": 30 * 24 * 60 * 60_000,
}


def timeframe_to_milliseconds(timeframe: str) -> int:
    """Convert an exchange timeframe code into milliseconds.

    Args:
        timeframe: CCXT timeframe string (e.g. ``"1m"`` or ``"1h"``).

    Returns:
        Duration in milliseconds.

    Raises:
        ValueError: If the timeframe value is unknown.
    """

    normalized = timeframe.strip()
    if not normalized:
        raise ValueError("Timeframe cannot be empty")

    if normalized == "1M":
        # Monthly timeframe uses an uppercase ``M`` to avoid clashing with minutes.
        pass
    else:
        normalized = normalized.lower()
    if normalized not in _TIMEFRAME_TO_MS:
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    return _TIMEFRAME_TO_MS[normalized]


def normalize_symbol(symbol: str, default_quote: str = "USDT") -> str:
    """Normalise trading symbols to CCXT's ``BASE/QUOTE`` representation.

    Examples::

        >>> normalize_symbol("BTC-USDT")
        'BTC/USDT'
        >>> normalize_symbol("ethusdt")
        'ETH/USDT'

    Args:
        symbol: Raw trading pair symbol from user configuration or exchange.
        default_quote: Quote currency used when the quote is not present.

    Returns:
        A normalised trading pair string in ``BASE/QUOTE`` form.

    Raises:
        ValueError: If the symbol is empty or cannot be parsed.
    """

    if not symbol or not symbol.strip():
        raise ValueError("Symbol cannot be empty")

    cleaned = symbol.strip().upper()

    for delimiter in ("/", "-", ":", "_"):
        if delimiter in cleaned:
            base, quote = cleaned.split(delimiter, 1)
            break
    else:
        # No explicit delimiter. Attempt to infer the quote currency by suffix.
        if cleaned.endswith(default_quote.upper()) and len(cleaned) > len(default_quote):
            base = cleaned[: -len(default_quote)]
            quote = default_quote
        else:
            base = cleaned
            quote = default_quote

    base, quote = base.strip(), quote.strip()
    if not base or not quote:
        raise ValueError(f"Invalid trading pair: {symbol}")

    return f"{base}/{quote}"


__all__ = [
    "timeframe_to_milliseconds",
    "normalize_symbol",
]
