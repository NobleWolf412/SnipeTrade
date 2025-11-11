"""Thin wrapper around CCXT exchanges with retry and parsing helpers."""

from __future__ import annotations

import time
from typing import Callable, List, Optional, Tuple

import ccxt

OHLCV = Tuple[int, float, float, float, float, float]


class CCXTAdapter:
    """Adapter that provides resilient OHLCV fetching from CCXT exchanges."""

    def __init__(
        self,
        exchange_id: str,
        config: Optional[dict] = None,
        *,
        max_retries: int = 3,
        retry_backoff: float = 0.5,
        sleep_func: Callable[[float], None] = time.sleep,
    ) -> None:
        if not hasattr(ccxt, exchange_id):
            raise ValueError(f"Exchange '{exchange_id}' is not available in CCXT")

        self.exchange_id = exchange_id
        self.config = config or {}
        self.max_retries = max(1, max_retries)
        self.retry_backoff = max(retry_backoff, 0.0)
        self._sleep = sleep_func
        self._exchange = getattr(ccxt, exchange_id)(self.config)

    @property
    def exchange(self):
        """Expose the underlying CCXT exchange instance."""

        return self._exchange

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        *,
        limit: int = 100,
        since: Optional[int] = None,
    ) -> List[OHLCV]:
        """Fetch OHLCV data, retrying on rate limit errors."""

        attempt = 0
        while True:
            attempt += 1
            try:
                raw_candles = self._exchange.fetch_ohlcv(symbol, timeframe, limit=limit, since=since)
                return [self._parse_ohlcv(candle) for candle in raw_candles]
            except ccxt.RateLimitExceeded as exc:
                if attempt >= self.max_retries:
                    raise
                delay = self.retry_backoff * attempt
                if delay > 0:
                    self._sleep(delay)
            except ccxt.NetworkError:
                # Surface network issues to callers for higher-level handling.
                raise
            except Exception as exc:  # pragma: no cover - defensive programming
                raise RuntimeError(f"Failed to fetch OHLCV for {symbol}: {exc}") from exc

    @staticmethod
    def _parse_ohlcv(candle: list) -> OHLCV:
        if len(candle) != 6:
            raise ValueError("CCXT OHLCV entries must have exactly 6 values")

        timestamp = int(candle[0])
        open_, high, low, close, volume = (float(candle[i]) for i in range(1, 6))
        return (timestamp, open_, high, low, close, volume)


__all__ = ["CCXTAdapter", "OHLCV"]
