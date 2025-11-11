"""CCXT exchange adapter with lightweight caching."""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import ccxt  # type: ignore

from snipetrade.models import OHLCVTuple
from snipetrade.utils.cache import TTLCache


DEFAULT_EXCHANGE = "phemex"


class CcxtAdapter:
    """Thin wrapper around CCXT exchanges that adds caching behaviour."""

    DEFAULT_TTLS = {
        "markets": 60 * 60,   # 1 hour
        "tickers": 30,        # 30 seconds
        "ohlcv": 60,          # 1 minute
    }

    def __init__(
        self,
        exchange_id: str = DEFAULT_EXCHANGE,
        config: Optional[Dict] = None,
        ttl_overrides: Optional[Dict[str, int]] = None,
    ) -> None:
        self.exchange_id = exchange_id.lower()
        exchange_class = getattr(ccxt, self.exchange_id)
        self.client = exchange_class(config or {})

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
    def load_markets(self, reload: bool = False) -> Dict:
        """Return exchange markets, optionally bypassing the cache."""

        cache_key = "markets"
        if reload:
            self._market_cache.pop(cache_key)

        cached = self._market_cache.get(cache_key)
        if cached is not None:
            return cached

        markets = self.client.load_markets(reload=reload)
        self._market_cache.set(cache_key, markets)
        return markets

    # ------------------------------------------------------------------
    # Public API mirroring old BaseExchange implementation
    # ------------------------------------------------------------------
    def get_top_pairs(self, limit: int = 50, quote_currency: str = "USDT") -> List[str]:
        """Get the most liquid pairs filtered by quote currency."""

        all_tickers = self._get_all_tickers()
        pairs: List[tuple[str, float]] = []

        for symbol, ticker in all_tickers.items():
            if quote_currency.upper() not in symbol.upper():
                continue
            quote_volume = ticker.get("quoteVolume") or ticker.get("quoteVolume24h")
            if quote_volume is None:
                continue
            try:
                volume = float(quote_volume)
            except (TypeError, ValueError):
                continue
            pairs.append((symbol, volume))

        pairs.sort(key=lambda item: item[1], reverse=True)
        return [symbol for symbol, _ in pairs[:limit]]

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 200,
        since: Optional[int] = None,
    ) -> List[OHLCVTuple]:
        """Fetch OHLCV data while caching results."""

        cache_key = self._ohlcv_cache_key(symbol, timeframe, limit, since)
        cached = self._ohlcv_cache.get(cache_key)
        if cached is not None:
            return cached

        candles = self.client.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
        typed_candles: List[OHLCVTuple] = []
        for entry in candles:
            if not entry or len(entry) < 6:
                continue
            try:
                typed_candles.append(self._cast_ohlcv_tuple(entry))
            except Exception:
                continue
        self._ohlcv_cache.set(cache_key, typed_candles)
        return typed_candles

    def get_current_price(self, symbol: str) -> float:
        """Return the most recent price for ``symbol``."""

        cache_key = f"ticker:{symbol}"
        cached = self._ticker_cache.get(cache_key)
        if cached is not None and "last" in cached:
            return float(cached["last"])

        ticker = self.client.fetch_ticker(symbol)
        if ticker:
            self._ticker_cache.set(cache_key, ticker)
            last_price = ticker.get("last") or ticker.get("close")
            if last_price is None:
                raise ValueError(f"Ticker for {symbol} did not include a price")
            return float(last_price)

        raise ValueError(f"No ticker data for {symbol}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_all_tickers(self) -> Dict[str, Dict]:
        cache_key = "tickers"
        cached = self._ticker_cache.get(cache_key)
        if cached is not None:
            return cached

        tickers = self.client.fetch_tickers()
        self._ticker_cache.set(cache_key, tickers)
        return tickers

    @staticmethod
    def _cast_ohlcv_tuple(entry: Sequence) -> OHLCVTuple:
        timestamp = int(entry[0])
        open_, high, low, close, volume = (
            float(entry[1]),
            float(entry[2]),
            float(entry[3]),
            float(entry[4]),
            float(entry[5]),
        )
        return OHLCVTuple(
            timestamp=timestamp,
            open=open_,
            high=high,
            low=low,
            close=close,
            volume=volume,
        )

    @staticmethod
    def _ohlcv_cache_key(
        symbol: str, timeframe: str, limit: int, since: Optional[int]
    ) -> str:
        return f"{symbol}:{timeframe}:{limit}:{since or 0}"


__all__ = ["CcxtAdapter", "DEFAULT_EXCHANGE"]

