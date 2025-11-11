"""CCXT-backed exchange adapter with hardened error handling."""

from __future__ import annotations

import logging
import random
import time
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional, Sequence

import ccxt

from .base import Exchange, ExchangeError, OHLCV, RateLimitError
from ..utils.symbols import normalize_symbol_for_exchange
from ..utils.timeframe import parse_tf_to_ms

LOG = logging.getLogger(__name__)


class CCXTExchangeAdapter(Exchange):
    """Concrete implementation of the :class:`~snipetrade.exchanges.base.Exchange` protocol."""

    _DEFAULT_BACKOFF_BASE = 0.5
    _BACKOFF_CAP = 10.0

    def __init__(
        self,
        exchange_id: str = "phemex",
        config: Optional[Dict[str, Any]] = None,
        *,
        market_cache_ttl: float = 300.0,
        max_retries: int = 5,
        backoff_base: float = _DEFAULT_BACKOFF_BASE,
    ) -> None:
        self.exchange_id = exchange_id.lower()
        self._config = config or {}
        self._market_cache_ttl = market_cache_ttl
        self._max_retries = max(1, max_retries)
        self._backoff_base = max(0.1, backoff_base)

        exchange_cls = getattr(ccxt, self.exchange_id)
        self._client = exchange_cls(self._config)

        self._markets_cache: MutableMapping[str, Mapping[str, Any]] = {}
        self._symbol_map: MutableMapping[str, str] = {}
        self._markets_expiry = 0.0

    # ---------------------------------------------------------------------
    # Protocol implementation
    # ------------------------------------------------------------------
    def fetch_markets(self, *, force_refresh: bool = False) -> Mapping[str, Mapping[str, Any]]:
        now = time.time()
        if not force_refresh and self._markets_cache and now < self._markets_expiry:
            return self._markets_cache

        raw_markets: Mapping[str, Mapping[str, Any]] = self._request_with_retries(self._client.load_markets)

        normalized: MutableMapping[str, Mapping[str, Any]] = {}
        symbol_map: MutableMapping[str, str] = {}
        for symbol, market in raw_markets.items():
            normalized_symbol = normalize_symbol_for_exchange(self.exchange_id, symbol)
            normalized[normalized_symbol] = market
            symbol_map[normalized_symbol] = market.get("symbol", symbol)

        self._markets_cache = normalized
        self._symbol_map = symbol_map
        self._markets_expiry = now + self._market_cache_ttl
        return self._markets_cache

    def fetch_ohlcv(self, symbol: str, timeframe: str, *, limit: int = 100) -> Sequence[OHLCV]:
        if limit <= 0:
            return []

        parse_tf_to_ms(timeframe)  # Validate timeframe input.
        self.fetch_markets()
        normalized_symbol = normalize_symbol_for_exchange(self.exchange_id, symbol)
        ccxt_symbol = self._symbol_map.get(normalized_symbol, symbol)

        raw_ohlcv = self._request_with_retries(
            self._client.fetch_ohlcv,
            ccxt_symbol,
            timeframe,
            limit=limit,
        )

        candles: list[OHLCV] = []
        for row in raw_ohlcv:
            if not isinstance(row, Iterable) or len(row) < 6:
                continue
            try:
                timestamp = int(row[0])
                open_, high, low, close, volume = (float(row[i]) for i in range(1, 6))
            except (TypeError, ValueError) as exc:  # pragma: no cover - defensive branch
                LOG.debug("Skipping malformed OHLCV row for %s: %s", normalized_symbol, exc)
                continue
            candles.append((timestamp, open_, high, low, close, volume))

        return candles

    def get_top_pairs(self, *, limit: int = 50, quote_currency: str = "USDT") -> Sequence[str]:
        quote_currency = quote_currency.upper()
        markets = self.fetch_markets()

        tickers: Mapping[str, Mapping[str, Any]] = {}
        try:
            tickers = self._request_with_retries(self._client.fetch_tickers)
        except RateLimitError:
            LOG.warning("Rate limit hit while fetching tickers; falling back to market metadata")
        except ExchangeError:
            LOG.warning("Unable to fetch tickers; falling back to market metadata")

        ranked: list[tuple[str, float]] = []

        if tickers:
            for symbol, ticker in tickers.items():
                normalized_symbol = normalize_symbol_for_exchange(self.exchange_id, symbol)
                if not normalized_symbol.endswith(f"/{quote_currency}"):
                    continue
                volume = _extract_volume(ticker)
                ranked.append((normalized_symbol, volume))

        if not ranked:
            for symbol, market in markets.items():
                if not symbol.endswith(f"/{quote_currency}"):
                    continue
                volume = _extract_volume(market.get("info", {}))
                ranked.append((symbol, volume))

        ranked.sort(key=lambda item: item[1], reverse=True)
        return [symbol for symbol, _ in ranked[:limit]]

    def get_current_price(self, symbol: str) -> float:
        markets = self.fetch_markets()
        normalized_symbol = normalize_symbol_for_exchange(self.exchange_id, symbol)
        ccxt_symbol = self._symbol_map.get(normalized_symbol, symbol)

        ticker = self._request_with_retries(self._client.fetch_ticker, ccxt_symbol)
        last = ticker.get("last") or ticker.get("close")
        if last is None:
            raise ExchangeError(f"Ticker for {symbol} did not include a last price")
        return float(last)

    # ------------------------------------------------------------------
    # Internal utilities
    # ------------------------------------------------------------------
    def _request_with_retries(self, func, *args, **kwargs):
        attempt = 0
        while True:
            try:
                return func(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 - we handle classification below
                attempt += 1
                should_retry, error = self._classify_exception(exc)
                if not should_retry or attempt >= self._max_retries:
                    raise error from exc

                delay = min(self._backoff_base * (2 ** (attempt - 1)), self._BACKOFF_CAP)
                jitter = random.uniform(0.5, 1.5)
                sleep_for = delay * jitter
                LOG.debug(
                    "Retrying %s after %.2fs due to %s (attempt %s/%s)",
                    func.__name__,
                    sleep_for,
                    error,
                    attempt,
                    self._max_retries,
                )
                time.sleep(sleep_for)

    def _classify_exception(self, exc: Exception) -> tuple[bool, ExchangeError]:
        if isinstance(exc, RateLimitError):  # pragma: no cover - defensive branch
            return True, exc

        if isinstance(exc, ccxt.RateLimitExceeded):
            return True, RateLimitError(str(exc))

        http_status = getattr(exc, "http_status", None) or getattr(exc, "status", None)
        if http_status == 429:
            return True, RateLimitError(str(exc))

        message = str(exc).lower()
        if "429" in message or "rate limit" in message:
            return True, RateLimitError(str(exc))

        if isinstance(exc, (ccxt.NetworkError, ccxt.RequestTimeout, ccxt.ExchangeNotAvailable)):
            return True, ExchangeError(str(exc))

        if isinstance(exc, ccxt.BaseError):
            return False, ExchangeError(str(exc))

        return True, ExchangeError(str(exc))


def _extract_volume(data: Mapping[str, Any]) -> float:
    for key in ("quoteVolume", "volume", "vol24h", "vol24hQuote"):
        value = data.get(key) if isinstance(data, Mapping) else None
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):  # pragma: no cover - fallback branch
                continue
    return 0.0


def create_exchange(
    exchange_id: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> CCXTExchangeAdapter:
    """Factory helper mirroring the previous imperative API."""

    resolved_id = (exchange_id or "phemex").lower()
    return CCXTExchangeAdapter(resolved_id, config=config, **kwargs)

