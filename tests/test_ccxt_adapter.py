"""Unit tests for the CCXT adapter module."""

import ccxt
import pytest

from snipetrade.exchanges.ccxt_adapter import CCXTAdapter, OHLCV


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
        def fetch_ohlcv(self, symbol, timeframe, limit=100, since=None):
            self.calls.append((symbol, timeframe, limit, since))
            return candles

    monkeypatch.setattr(ccxt, "phemex", DummyExchange)
    adapter = CCXTAdapter("phemex", {"enableRateLimit": True})

    result = adapter.fetch_ohlcv("BTC/USDT", "1m", limit=2)

    assert all(isinstance(entry, tuple) for entry in result)
    assert result[0] == pytest.approx((1700000000000, 100.0, 110.0, 90.0, 105.0, 1200.0))
    assert isinstance(result[0], tuple) and len(result[0]) == len(OHLCV.__args__)  # type: ignore[attr-defined]


def test_rate_limit_retries_with_backoff(monkeypatch):
    """Rate limit errors should trigger retries with linear backoff."""

    attempts = {"count": 0}
    sleeps = []

    class RateLimitedExchange(_DummyBase):
        def fetch_ohlcv(self, symbol, timeframe, limit=100, since=None):
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise ccxt.RateLimitExceeded("Too many requests")
            return [[1700000000000, 1, 1, 1, 1, 1]]

    def fake_sleep(delay):
        sleeps.append(delay)

    monkeypatch.setattr(ccxt, "phemex", RateLimitedExchange)
    adapter = CCXTAdapter("phemex", max_retries=3, retry_backoff=0.25, sleep_func=fake_sleep)

    candles = adapter.fetch_ohlcv("BTC/USDT", "1m")

    assert attempts["count"] == 3
    assert sleeps == [0.25, 0.5]
    assert candles[0][0] == 1700000000000


def test_network_error_is_raised(monkeypatch):
    """Network errors should bubble up for upstream handling."""

    class FailingExchange(_DummyBase):
        def fetch_ohlcv(self, symbol, timeframe, limit=100, since=None):
            raise ccxt.NetworkError("Connection down")

    monkeypatch.setattr(ccxt, "phemex", FailingExchange)
    adapter = CCXTAdapter("phemex", max_retries=2)

    with pytest.raises(ccxt.NetworkError):
        adapter.fetch_ohlcv("BTC/USDT", "1m")
