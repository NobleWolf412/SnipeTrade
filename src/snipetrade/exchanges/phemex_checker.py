"""Helpers specific to Phemex exchange nuances."""

from __future__ import annotations

from .base import Exchange
from ..utils.symbols import normalize_symbol_for_exchange


def is_pair_on_phemex(exchange: Exchange, symbol: str) -> bool:
    """Return True when the adapter confirms the pair is tradable on Phemex."""

    if exchange.exchange_id.lower() != "phemex":
        return False

    normalized_symbol = normalize_symbol_for_exchange("phemex", symbol)
    markets = exchange.fetch_markets()
    market = markets.get(normalized_symbol)
    if not market:
        return False

    if "active" in market:
        return bool(market["active"])
    if "info" in market and isinstance(market["info"], dict):
        return bool(market["info"].get("status", "") not in {"Closed", "Suspended"})

    return True

