"""Core exchange protocol definitions and shared types."""

from __future__ import annotations

from typing import Mapping, Protocol, Sequence, TypeAlias, runtime_checkable, Any

__all__ = [
    "Exchange",
    "ExchangeError",
    "RateLimitError",
    "OHLCV",
]


OHLCV: TypeAlias = "tuple[int, float, float, float, float, float]"
"""Typed representation of an OHLCV candle (ms, open, high, low, close, volume)."""


class ExchangeError(RuntimeError):
    """Generic exchange failure."""


class RateLimitError(ExchangeError):
    """Raised when an exchange request exceeds the rate limit."""


@runtime_checkable
class Exchange(Protocol):
    """Protocol describing the behaviour required from exchange adapters."""

    exchange_id: str

    def fetch_markets(self, *, force_refresh: bool = False) -> Mapping[str, Mapping[str, Any]]:
        """Return the exchange markets map using an internal cache when possible."""

    def fetch_ohlcv(self, symbol: str, timeframe: str, *, limit: int = 100) -> Sequence[OHLCV]:
        """Fetch historical candles for a trading pair/timeframe combination."""

    def get_top_pairs(self, *, limit: int = 50, quote_currency: str = "USDT") -> Sequence[str]:
        """Return the most actively traded pairs for the provided quote currency."""

    def get_current_price(self, symbol: str) -> float:
        """Return the latest trade price for the provided symbol."""

