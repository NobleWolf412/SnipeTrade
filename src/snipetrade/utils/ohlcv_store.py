"""Disk-backed storage for OHLCV caches used by tests and tooling."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = ["open", "high", "low", "close", "volume"]


class OhlcvStore:
    """Simple filesystem cache for OHLCV time-series data."""

    def __init__(self, cache_dir: Path | str) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_cache_path(self, symbol: str, timeframe: str) -> Path:
        """Return the filesystem path where the OHLCV cache is stored."""

        safe_symbol = symbol.replace("/", "_")
        return self.cache_dir / f"{safe_symbol}_{timeframe}.csv"

    def write(self, symbol: str, timeframe: str, data: pd.DataFrame) -> Path:
        """Persist OHLCV data to disk after validation."""

        self._validate_frame(data)

        frame = data.copy()
        if frame.index.tz is None:
            frame.index = frame.index.tz_localize("UTC")
        else:
            frame.index = frame.index.tz_convert("UTC")

        if not frame.index.is_monotonic_increasing:
            frame = frame.sort_index()

        frame.index.name = "timestamp"
        path = self.get_cache_path(symbol, timeframe)
        frame.to_csv(path, float_format="%.10f")
        return path

    def read(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Load cached OHLCV data as a timezone aware, monotonic frame."""

        path = self.get_cache_path(symbol, timeframe)
        if not path.exists():
            raise FileNotFoundError(path)

        frame = pd.read_csv(path, parse_dates=["timestamp"], index_col="timestamp")
        if frame.empty:
            frame.index = frame.index.tz_localize("UTC")
            return frame

        if frame.index.tz is None:
            frame.index = frame.index.tz_localize("UTC")
        else:
            frame.index = frame.index.tz_convert("UTC")

        if not frame.index.is_monotonic_increasing:
            frame = frame.sort_index()

        self._validate_frame(frame)
        return frame

    @staticmethod
    def _validate_frame(frame: pd.DataFrame) -> None:
        missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
        if missing:
            raise ValueError(f"Missing columns: {', '.join(missing)}")

        if not isinstance(frame.index, pd.DatetimeIndex):
            raise ValueError("DataFrame index must be a DatetimeIndex")


__all__ = ["OhlcvStore", "REQUIRED_COLUMNS"]
