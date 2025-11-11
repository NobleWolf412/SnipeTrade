"""Utility helpers for working with exchange-specific symbols."""

from __future__ import annotations


def normalize_symbol_for_exchange(exchange_id: str, symbol: str) -> str:
    """Normalise pair notation so cache lookups remain consistent."""

    cleaned = symbol.strip().upper()
    cleaned = cleaned.replace('-', '/').replace(':', '/').replace(' ', '')

    if '/' not in cleaned and len(cleaned) > 4:
        base, quote = cleaned[:-4], cleaned[-4:]
        cleaned = f"{base}/{quote}"

    if exchange_id.lower() == "phemex" and cleaned.endswith("/USDTUSDT"):
        cleaned = cleaned.replace("/USDTUSDT", "/USDT")

    return cleaned
