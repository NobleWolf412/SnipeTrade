"""Unified CCXT exchange adapter with caching and robust error handling."""

from __future__ import annotations

import logging
import random
import time
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence

import ccxt

from ..models import OHLCVTuple
from ..utils.cache import TTLCache
from ..utils.symbols import normalize_symbol_for_exchange
from ..utils.timeframe import parse_tf_to_ms

LOG = logging.getLogger(__name__)


class UnifiedCCXTAdapter:
    """Unified CCXT adapter with caching and retry logic."""

    DEFAULT_TTLS = {
        "markets": 60 * 60,   # 1 hour
        "tickers": 30,        # 30 seconds
        "ohlcv": 60,          # 1 minute
    }

    _DEFAULT_BACKOFF_BASE = 0.5
    _BACKOFF_CAP = 10.0

    def __init__(
        self,
        exchange_id: str = "phemex",
        config: Optional[Dict[str, Any]] = None,
        ttl_overrides: Optional[Dict[str, int]] = None,
        *,
        market_cache_ttl: float = 300.0,
        max_retries: int = 5,
        backoff_base: float = _DEFAULT_BACKOFF_BASE,
    ) -> None:
        self.exchange_id = exchange_id.lower()
        self._config = config or {}
        self._market_cache_ttl = market_cache_ttl
        self._max_retries = max(1, max_retries)
        self._backoff_base = max(0.1, backoff_base)

        exchange_cls = getattr(ccxt, self.exchange_id)
        self._client = exchange_cls(self._config)

        self.ttl_overrides = {**self.DEFAULT_TTLS, **(ttl_overrides or {})}
        self._market_cache: TTLCache[str, Dict] = TTLCache(
            self.ttl_overrides["markets"]
        )
        self._ticker_cache: TTLCache[str, Dict] = TTLCache(
            self.ttl_overrides["tickers"]
        )
        self._ohlcv_cache: TTLCache[str, List[OHLCVTuple]] = TTLCache(
            self.ttl_overrides["ohlcv"]
        )

    # ------------------------------------------------------------------
    # Market helpers
    # ------------------------------------------------------------------
    def fetch_markets(self, *, force_refresh: bool = False) -> Mapping[str, Mapping[str, Any]]:
        """Return exchange markets, optionally bypassing the cache."""

        cache_key = "markets"
        if not force_refresh:
            cached = self._market_cache.get(cache_key)
            if cached is not None:
                return cached

        raw_markets: Mapping[str, Mapping[str, Any]] = self._request_with_retries(self._client.load_markets)

        normalized: MutableMapping[str, Mapping[str, Any]] = {}
        for symbol, market in raw_markets.items():
            normalized_symbol = normalize_symbol_for_exchange(self.exchange_id, symbol)
            normalized[normalized_symbol] = market

        self._market_cache.set(cache_key, normalized)
        return normalized

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 200,
        since: Optional[int] = None,
    ) -> List[OHLCVTuple]:
        """Fetch OHLCV data while caching results."""

        cache_key = f"ohlcv:{symbol}:{timeframe}:{limit}:{since or 0}"
        cached = self._ohlcv_cache.get(cache_key)
        if cached is not None:
            return cached

        raw_ohlcv = self._request_with_retries(
            self._client.fetch_ohlcv,
            symbol,
            timeframe,
            limit=limit,
            since=since,
        )

        typed_candles: List[OHLCVTuple] = []
        for row in raw_ohlcv:
            if not isinstance(row, Iterable) or len(row) < 6:
                continue
            try:
                timestamp = int(row[0])
                open_, high, low, close, volume = (float(row[i]) for i in range(1, 6))
                typed_candles.append(OHLCVTuple(timestamp, open_, high, low, close, volume))
            except (TypeError, ValueError):
                continue

        self._ohlcv_cache.set(cache_key, typed_candles)
        return typed_candles

    def get_top_pairs(self, *, limit: int = 50, quote_currency: str = "USDT") -> Sequence[str]:
        """Get the most liquid pairs filtered by quote currency."""

        markets = self.fetch_markets()
        ranked: list[tuple[str, float]] = []

        tickers = self._request_with_retries(self._client.fetch_tickers)
        for symbol, ticker in tickers.items():
            normalized_symbol = normalize_symbol_for_exchange(self.exchange_id, symbol)
            if not normalized_symbol.endswith(f"/{quote_currency}"):
                continue
            volume = ticker.get("quoteVolume") or ticker.get("volume")
            if volume is not None:
                try:
                    ranked.append((normalized_symbol, float(volume)))
                except (TypeError, ValueError):
                    continue

        ranked.sort(key=lambda item: item[1], reverse=True)
        return [symbol for symbol, _ in ranked[:limit]]

    def get_current_price(self, symbol: str) -> float:
        """Return the most recent price for ``symbol``."""

        cache_key = f"ticker:{symbol}"
        cached = self._ticker_cache.get(cache_key)
        if cached is not None and "last" in cached:
            return float(cached["last"])

        ticker = self._request_with_retries(self._client.fetch_ticker, symbol)
        if ticker:
            self._ticker_cache.set(cache_key, ticker)
            last_price = ticker.get("last") or ticker.get("close")
            if last_price is None:
                raise ValueError(f"Ticker for {symbol} did not include a price")
            return float(last_price)

        raise ValueError(f"No ticker data for {symbol}")

    # ------------------------------------------------------------------
    # Internal utilities
    # ------------------------------------------------------------------
    def _request_with_retries(self, func, *args, **kwargs):
        attempt = 0
        while True:
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                attempt += 1
                if attempt >= self._max_retries:
                    raise

                delay = min(self._backoff_base * (2 ** (attempt - 1)), self._BACKOFF_CAP)
                jitter = random.uniform(0.5, 1.5)
                time.sleep(delay * jitter)


__all__ = ["UnifiedCCXTAdapter"]

