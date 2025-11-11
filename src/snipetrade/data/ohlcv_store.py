"""Persistent OHLCV cache helpers."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Iterable, Literal, Optional, Union, cast

import pandas as pd
from pandas import DataFrame

from snipetrade import config as app_config

try:  # pragma: no cover - optional dependency check
    import pyarrow  # type: ignore  # noqa: F401

    _PYARROW_AVAILABLE = True
except ImportError:  # pragma: no cover - handled at runtime
    _PYARROW_AVAILABLE = False

CacheFormat = Literal["parquet", "feather"]

REQUIRED_COLUMNS: Iterable[str] = ("open", "high", "low", "close", "volume")
_DEFAULT_CACHE_DIR = Path(getattr(app_config, "OHLCV_CACHE_DIR", ".cache/ohlcv")).expanduser()
_DEFAULT_TTL_MS = int(getattr(app_config, "OHLCV_CACHE_TTL_MS", 300_000))
_DEFAULT_FORMAT = getattr(app_config, "OHLCV_CACHE_FORMAT", "parquet")


def _resolve_format(storage_format: Optional[str]) -> CacheFormat:
    fmt = (storage_format or _DEFAULT_FORMAT or "parquet").lower()
    if fmt not in {"parquet", "feather"}:
        raise ValueError(f"Unsupported storage format: {fmt}")
    return cast(CacheFormat, fmt)


def _resolve_cache_dir(cache_dir: Optional[Union[str, Path]]) -> Path:
    directory = (
        Path(cache_dir).expanduser() if cache_dir is not None else _DEFAULT_CACHE_DIR
    )
    return directory


def _require_pyarrow(action: str) -> None:
    if not _PYARROW_AVAILABLE:
        raise RuntimeError(
            "pyarrow is required to "
            f"{action}. Install the 'pyarrow' package to enable OHLCV caching."
        )


def _sanitize_key(symbol: str, timeframe: str) -> str:
    symbol_key = symbol.replace("/", "_").replace(":", "_").replace(" ", "").lower()
    timeframe_key = timeframe.replace(" ", "").replace("/", "_").lower()
    return f"{symbol_key}__{timeframe_key}"


def _cache_path(symbol: str, timeframe: str, cache_dir: Optional[Union[str, Path]], storage_format: CacheFormat) -> Path:
    directory = _resolve_cache_dir(cache_dir)
    extension = "parquet" if storage_format == "parquet" else "feather"
    return directory / f"{_sanitize_key(symbol, timeframe)}.{extension}"


def _ensure_cache_dir(path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except FileExistsError:
        # Another process might have created the directory concurrently.
        pass


def _is_expired(path: Path, ttl_ms: int) -> bool:
    if ttl_ms <= 0:
        return False
    try:
        modified = path.stat().st_mtime
    except FileNotFoundError:
        return True
    age_ms = (time.time() - modified) * 1000.0
    return age_ms > ttl_ms


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError:
        return


def _normalise_dataframe(frame: DataFrame) -> DataFrame:
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise TypeError("OHLCV data must use a DatetimeIndex")

    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"OHLCV data missing required columns: {', '.join(missing)}")

    normalised = frame.copy()
    index = normalised.index
    if index.tz is None:
        index = index.tz_localize("UTC")
    else:
        index = index.tz_convert("UTC")

    if not index.is_monotonic_increasing:
        order = index.argsort()
        normalised = normalised.iloc[order]
        index = index[order]

    # Deduplicate by keeping the most recent value per timestamp
    if not index.is_unique:
        deduped = ~index.duplicated(keep="last")
        normalised = normalised[deduped]
        index = index[deduped]

    normalised.index = index
    normalised.index.name = "timestamp"
    return normalised


def _write_parquet(path: Path, frame: DataFrame) -> None:
    _require_pyarrow("write parquet caches")
    frame.to_parquet(path, engine="pyarrow")


def _write_feather(path: Path, frame: DataFrame) -> None:
    _require_pyarrow("write feather caches")
    temp = frame.reset_index()
    if "timestamp" not in temp.columns and "index" in temp.columns:
        temp = temp.rename(columns={"index": "timestamp"})
    temp.to_feather(path)


def _read_parquet(path: Path) -> DataFrame:
    _require_pyarrow("read parquet caches")
    return pd.read_parquet(path, engine="pyarrow")


def _read_feather(path: Path) -> DataFrame:
    _require_pyarrow("read feather caches")
    frame = pd.read_feather(path)
    if "timestamp" not in frame.columns:
        raise ValueError("Feather cache missing 'timestamp' column")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame = frame.set_index("timestamp")
    frame.index.name = "timestamp"
    return frame


def get_cached(
    symbol: str,
    timeframe: str,
    *,
    cache_dir: Optional[Union[str, Path]] = None,
    storage_format: Optional[str] = None,
    ttl_ms: Optional[int] = None,
) -> Optional[DataFrame]:
    """Load cached OHLCV data if present and fresh."""

    fmt = _resolve_format(storage_format)
    path = _cache_path(symbol, timeframe, cache_dir, fmt)

    if not path.exists():
        return None

    ttl = int(ttl_ms if ttl_ms is not None else _DEFAULT_TTL_MS)
    if _is_expired(path, ttl):
        _safe_unlink(path)
        return None

    try:
        frame = _read_parquet(path) if fmt == "parquet" else _read_feather(path)
        return _normalise_dataframe(frame)
    except Exception:
        _safe_unlink(path)
        return None


def put_cached(
    symbol: str,
    timeframe: str,
    frame: DataFrame,
    *,
    cache_dir: Optional[Union[str, Path]] = None,
    storage_format: Optional[str] = None,
) -> Path:
    """Persist OHLCV data to the cache and return the cache path."""

    fmt = _resolve_format(storage_format)
    path = _cache_path(symbol, timeframe, cache_dir, fmt)
    _ensure_cache_dir(path)

    normalised = _normalise_dataframe(frame)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    _safe_unlink(temp_path)
    if fmt == "parquet":
        _write_parquet(temp_path, normalised)
    else:
        _write_feather(temp_path, normalised)

    os.replace(temp_path, path)
    return path

