"""Phemex exchange adapter."""

from __future__ import annotations

from typing import Dict

from .base import ExchangeAdapter


class PhemexAdapter(ExchangeAdapter):
    def __init__(self, client, symbols):
        super().__init__(name="phemex")
        self.client = client
        self.symbols = set(symbols)

    def is_symbol_supported(self, symbol: str) -> bool:
        return symbol in self.symbols

    def best_price(self, symbol: str) -> float:
        ticker = self.client.fetch_ticker(symbol)
        return float(ticker.get("ask") or ticker.get("last") or 0.0)

    def submit_order(self, symbol: str, size: float, price: float) -> Dict[str, float]:
        order = self.client.create_order(symbol, "limit", "buy" if size > 0 else "sell", abs(size), price)
        return {"order_id": order.get("id"), "exchange": self.name, "price": price, "size": size}
