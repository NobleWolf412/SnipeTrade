"""Common interface for exchange adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class ExchangeAdapter:
    name: str

    def is_symbol_supported(self, symbol: str) -> bool:
        raise NotImplementedError

    def best_price(self, symbol: str) -> float:
        raise NotImplementedError

    def submit_order(self, symbol: str, size: float, price: float) -> Dict[str, float]:
        raise NotImplementedError
