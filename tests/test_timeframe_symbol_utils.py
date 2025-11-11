"""Tests for timeframe conversion and symbol normalisation helpers."""

import pytest

from snipetrade.utils.timeframe_symbol import normalize_symbol, timeframe_to_milliseconds


@pytest.mark.parametrize(
    "timeframe,expected",
    [
        ("1m", 60_000),
        ("15m", 15 * 60_000),
        ("1h", 60 * 60_000),
        ("4h", 4 * 60 * 60_000),
        ("1d", 24 * 60 * 60_000),
        ("1w", 7 * 24 * 60 * 60_000),
        ("1M", 30 * 24 * 60 * 60_000),
    ],
)
def test_timeframe_to_milliseconds(timeframe, expected):
    """Ensure timeframe conversion returns the expected duration."""

    assert timeframe_to_milliseconds(timeframe) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("BTC-USDT", "BTC/USDT"),
        ("ETHUSDT", "ETH/USDT"),
        ("sol", "SOL/USDT"),
        ("XRP/USDC", "XRP/USDC"),
        ("ada_usdt", "ADA/USDT"),
    ],
)
def test_normalize_symbol_variants(raw, expected):
    """Different exchange symbol formats should normalise consistently."""

    assert normalize_symbol(raw) == expected


def test_timeframe_invalid_value():
    with pytest.raises(ValueError):
        timeframe_to_milliseconds("7x")


def test_normalize_symbol_empty():
    with pytest.raises(ValueError):
        normalize_symbol("")
