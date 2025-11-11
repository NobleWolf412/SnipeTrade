"""Exchange connector modules for multi-exchange support."""

from .base import Exchange, ExchangeError, OHLCV, RateLimitError
from .ccxt_adapter import CcxtAdapter as UnifiedCCXTAdapter, create_exchange, CcxtAdapter
from .phemex_checker import is_pair_on_phemex
from .offline_adapter import CcxtAdapter as OfflineCcxtAdapter, CachedOHLCV
from ..utils.symbols import normalize_symbol_for_exchange

__all__ = [
    "Exchange",
    "ExchangeError",
    "RateLimitError",
    "OHLCV",
    "UnifiedCCXTAdapter",
    "create_exchange",
    "is_pair_on_phemex",
    "OfflineCcxtAdapter",
    "CachedOHLCV",
    "CcxtAdapter",
    "normalize_symbol_for_exchange",
]
