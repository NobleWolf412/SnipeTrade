"""Unit tests for the CCXT adapter module."""

import ccxt
import pytest

from snipetrade.exchanges import UnifiedCCXTAdapter, OHLCV


class _DummyBase:
    def __init__(self, _config=None):
        self.calls = []


def test_fetch_ohlcv_returns_typed_tuples(monkeypatch):
    """The adapter should coerce CCXT responses into typed OHLCV tuples."""

    candles = [
        [1700000000000, "100", "110", "90", "105", "1200"],
        [1700000060000, "105", "115", "95", "110", "1500"],
    ]

    class DummyExchange(_DummyBase):
        def load_markets(self):
            """Mock method for fetching markets."""
            return {"BTC/USDT": {"id": "BTCUSDT", "symbol": "BTC/USDT"}}
        
        def fetch_ohlcv(self, symbol, timeframe, limit=100, since=None):
            self.calls.append((symbol, timeframe, limit, since))
            return candles

    monkeypatch.setattr(ccxt, "phemex", DummyExchange)
    adapter = UnifiedCCXTAdapter("phemex", {"enableRateLimit": True})

    result = adapter.fetch_ohlcv("BTC/USDT", "1m", limit=2)

    assert all(isinstance(entry, tuple) for entry in result)
    assert result[0] == pytest.approx((1700000000000, 100.0, 110.0, 90.0, 105.0, 1200.0))
    assert isinstance(result[0], tuple) and len(result[0]) == 6


def test_rate_limit_retries_with_backoff(monkeypatch):
    """Rate limit errors should trigger retries with exponential backoff."""

    attempts = {"count": 0}

    class RateLimitedExchange(_DummyBase):
        def load_markets(self):
            return {"BTC/USDT": {"id": "BTCUSDT", "symbol": "BTC/USDT"}}
        
        def fetch_ohlcv(self, symbol, timeframe, limit=100, since=None):
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise ccxt.RateLimitExceeded("Too many requests")
            return [[1700000000000, 1, 1, 1, 1, 1]]

    monkeypatch.setattr(ccxt, "phemex", RateLimitedExchange)
    monkeypatch.setattr("time.sleep", lambda x: None)  # Skip actual sleep in tests
    adapter = UnifiedCCXTAdapter("phemex", max_retries=3, backoff_base=0.25)

    candles = adapter.fetch_ohlcv("BTC/USDT", "1m")

    assert attempts["count"] == 3
    assert candles[0][0] == 1700000000000


def test_network_error_is_raised(monkeypatch):
    """Network errors should bubble up for upstream handling."""

    class FailingExchange(_DummyBase):
        def load_markets(self):
            return {"BTC/USDT": {"id": "BTCUSDT", "symbol": "BTC/USDT"}}
        
        def fetch_ohlcv(self, symbol, timeframe, limit=100, since=None):
            raise ccxt.NetworkError("Connection down")

    from snipetrade.exchanges.base import ExchangeError
    
    monkeypatch.setattr(ccxt, "phemex", FailingExchange)
    adapter = UnifiedCCXTAdapter("phemex", max_retries=2)

    with pytest.raises(ExchangeError, match="Connection down"):
        adapter.fetch_ohlcv("BTC/USDT", "1m")
