"""Smart order router across multiple exchanges."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

from .adapters.base import ExchangeAdapter


@dataclass
class RouteDecision:
    exchange: str
    symbol: str
    size: float
    price: float


class SmartRouter:
    def __init__(self, adapters: Iterable[ExchangeAdapter]) -> None:
        self.adapters = {adapter.name: adapter for adapter in adapters}

    def price_snapshot(self, symbol: str) -> Dict[str, float]:
        return {name: adapter.best_price(symbol) for name, adapter in self.adapters.items()}

    def route(self, symbol: str, size: float) -> RouteDecision:
        quotes = {
            name: adapter.best_price(symbol)
            for name, adapter in self.adapters.items()
            if adapter.is_symbol_supported(symbol)
        }
        if not quotes:
            raise ValueError(f"no liquidity for {symbol}")
        exchange, price = min(quotes.items(), key=lambda kv: kv[1])
        return RouteDecision(exchange=exchange, symbol=symbol, size=size, price=price)

    def execute(self, symbol: str, size: float) -> Dict[str, float]:
        decision = self.route(symbol, size)
        adapter = self.adapters[decision.exchange]
        return adapter.submit_order(symbol, size, decision.price)
