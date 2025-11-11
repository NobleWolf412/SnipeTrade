"""Offline-friendly CCXT adapter with local OHLCV cache support."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from snipetrade.models import MarketData, TradeSetup


def _parse_timestamp(value: str) -> datetime:
    """Parse ISO-8601 timestamps that may use the trailing Z suffix."""

    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


@dataclass
class CachedOHLCV:
    """Container for cached OHLCV metadata."""

    symbol: str
    timeframe: str
    path: Path


class CcxtAdapter:
    """Minimal adapter that reads OHLCV data from the bundled cache."""

    def __init__(self, exchange: str, cache_dir: Optional[Path] = None, candles_per_request: int = 200):
        self.exchange = exchange
        root_cache = Path(cache_dir) if cache_dir else Path(__file__).resolve().parents[3] / "data" / "ohlcv_cache"
        self.exchange_cache = root_cache / exchange.lower()
        self.candles_per_request = candles_per_request

    def _cache_file(self, symbol: str, timeframe: str) -> Path:
        symbol_slug = symbol.replace("/", "")
        return self.exchange_cache / symbol_slug / f"{timeframe}.json"

    def list_cached_symbols(self) -> List[str]:
        if not self.exchange_cache.exists():
            return []
        symbols = []
        for child in self.exchange_cache.iterdir():
            if child.is_dir():
                symbols.append(child.name)
        return symbols

    def load_ohlcv(self, symbol: str, timeframe: str, limit: Optional[int] = None) -> List[MarketData]:
        """Load OHLCV candles from the cache."""

        file_path = self._cache_file(symbol, timeframe)
        if not file_path.exists():
            raise FileNotFoundError(
                f"Cached OHLCV not found for {symbol} {timeframe} on {self.exchange}: {file_path}"
            )

        candles = json.loads(file_path.read_text())
        if limit:
            candles = candles[-limit:]

        market_data: List[MarketData] = []
        for candle in candles:
            market_data.append(
                MarketData(
                    symbol=symbol,
                    exchange=self.exchange,
                    timeframe=timeframe,
                    timestamp=_parse_timestamp(candle["timestamp"]),
                    open=float(candle["open"]),
                    high=float(candle["high"]),
                    low=float(candle["low"]),
                    close=float(candle["close"]),
                    volume=float(candle["volume"]),
                )
            )
        return market_data

    def scan_symbol(
        self,
        symbol: str,
        timeframes: Sequence[str],
        scorer,
        limit: Optional[int] = None,
    ) -> Optional[TradeSetup]:
        """Score a single symbol using cached OHLCV data."""

        timeframe_data: Dict[str, List[MarketData]] = {}
        for timeframe in timeframes:
            try:
                candles = self.load_ohlcv(symbol, timeframe, limit=limit or self.candles_per_request)
            except FileNotFoundError:
                continue
            if len(candles) >= 50:
                timeframe_data[timeframe] = candles

        if not timeframe_data:
            return None

        # Use the highest-resolution timeframe that returned candles for the price reference.
        for timeframe in timeframes:
            if timeframe in timeframe_data:
                current_price = timeframe_data[timeframe][-1].close
                break
        else:
            current_price = next(iter(timeframe_data.values()))[-1].close

        return scorer.score_setup(
            symbol=symbol,
            exchange=self.exchange,
            timeframe_data=timeframe_data,
            current_price=current_price,
        )

    def available_cached_pairs(self) -> List[CachedOHLCV]:
        """Return metadata for every cached OHLCV file."""

        metadata: List[CachedOHLCV] = []
        if not self.exchange_cache.exists():
            return metadata

        for symbol_dir in self.exchange_cache.iterdir():
            if not symbol_dir.is_dir():
                continue
            symbol = symbol_dir.name
            for timeframe_file in symbol_dir.glob("*.json"):
                metadata.append(
                    CachedOHLCV(
                        symbol=symbol,
                        timeframe=timeframe_file.stem,
                        path=timeframe_file,
                    )
                )
        return metadata

__all__ = ["CcxtAdapter", "CachedOHLCV"]
