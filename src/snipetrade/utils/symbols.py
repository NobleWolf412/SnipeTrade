"""Symbol formatting helpers for exchange interoperability."""

from __future__ import annotations

__all__ = ["normalize_symbol_for_exchange"]


def normalize_symbol_for_exchange(symbol: str, exchange: str = "phemex") -> str:
    """Normalize a market symbol for use with a specific exchange.

    Currently the normalization strategy is exchange agnostic but the
    ``exchange`` argument is accepted for future compatibility.

    Args:
        symbol: The input market symbol (e.g. ``btc-usdt`` or ``eth``).
        exchange: Target exchange identifier. Defaults to ``"phemex"``.

    Returns:
        Normalized trading pair symbol (e.g. ``BTC/USDT``).

    Raises:
        ValueError: If the provided symbol is empty.
    """

    if not isinstance(symbol, str):
        raise ValueError("Symbol must be provided as a string")

    cleaned = symbol.strip()
    if not cleaned:
        raise ValueError("Symbol cannot be empty")

    normalized = cleaned.replace("-", "/").upper()

    parts = [part for part in normalized.split("/") if part]

    if not parts:
        raise ValueError("Symbol must contain at least a base asset")

    base = parts[0]
    quote = parts[1] if len(parts) > 1 else "USDT"

    return f"{base}/{quote}"
