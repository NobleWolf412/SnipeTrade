"""Helpers for working with the Phemex markets."""

from __future__ import annotations

from typing import Optional, Set

from snipetrade.adapters import CcxtAdapter, DEFAULT_EXCHANGE
from snipetrade.utils.cache import TTLCache


_MARKET_CACHE = TTLCache[str, Set[str]](ttl_seconds=60 * 30)  # 30 minutes


def _load_supported_pairs(adapter: CcxtAdapter) -> Set[str]:
    cache_key = f"markets:{adapter.exchange_id}"
    cached = _MARKET_CACHE.get(cache_key)
    if cached is not None:
        return cached

    try:
        markets = adapter.load_markets()
    except Exception:
        markets = {}

    symbols = set(markets.keys()) if isinstance(markets, dict) else set()
    _MARKET_CACHE.set(cache_key, symbols)
    return symbols


def is_pair_on_phemex(symbol: str, adapter: Optional[CcxtAdapter] = None) -> bool:
    """Return ``True`` if ``symbol`` is listed on Phemex.

    For non-Phemex exchanges the function always returns ``True`` to avoid
    unnecessarily filtering pairs when the adapter targets another exchange.
    """

    if not symbol:
        return False

    active_adapter = adapter or CcxtAdapter(DEFAULT_EXCHANGE)
    if active_adapter.exchange_id != "phemex":
        return True

    supported_pairs = _load_supported_pairs(active_adapter)
    if not supported_pairs:
        # If we cannot determine the supported markets we avoid false negatives.
        return True
    return symbol in supported_pairs


__all__ = ["is_pair_on_phemex"]

