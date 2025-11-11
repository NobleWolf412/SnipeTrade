"""Tests for the OHLCV cache store utility."""

from pathlib import Path
import shutil

import pandas as pd
import pytest

from snipetrade.utils.ohlcv_store import OhlcvStore, REQUIRED_COLUMNS


@pytest.fixture
def sample_frame():
    index = pd.date_range("2024-01-01", periods=3, freq="H", tz="UTC")
    index.name = "timestamp"
    data = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 102.0, 103.0],
            "low": [99.0, 100.0, 101.5],
            "close": [100.5, 101.5, 102.5],
            "volume": [1500.0, 1600.0, 1700.0],
        },
        index=index,
    )
    return data


def test_roundtrip_write_read(tmp_path, sample_frame):
    store = OhlcvStore(tmp_path)

    store.write("BTC/USDT", "1h", sample_frame)
    loaded = store.read("BTC/USDT", "1h")

    pd.testing.assert_frame_equal(loaded, sample_frame, check_freq=False)


def test_write_missing_columns(tmp_path, sample_frame):
    store = OhlcvStore(tmp_path)
    incomplete = sample_frame.drop(columns=["high", "low"])

    with pytest.raises(ValueError) as exc:
        store.write("ETH/USDT", "1h", incomplete)

    for column in ("high", "low"):
        assert column in str(exc.value)


def test_read_enforces_monotonic_utc(tmp_path):
    store = OhlcvStore(tmp_path)
    fixture_path = Path(__file__).parent / "fixtures" / "sample_ohlcv.csv"
    target = store.get_cache_path("BTC/USDT", "1h")
    shutil.copy(fixture_path, target)

    frame = store.read("BTC/USDT", "1h")

    assert frame.index.tz is not None and str(frame.index.tz) == "UTC"
    assert frame.index.is_monotonic_increasing
    assert list(frame.columns) == REQUIRED_COLUMNS
