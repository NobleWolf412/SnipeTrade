"""Simple trade-tape derived metrics."""

from __future__ import annotations

from typing import Dict, Iterable


def _extract_qty(trade: Dict) -> float:
    for key in ("qty", "size", "amount", "volume"):
        if key in trade:
            try:
                return float(trade[key])
            except (TypeError, ValueError):
                continue
    return 0.0


def _extract_side(trade: Dict) -> str:
    side = trade.get("side")
    if side:
        return str(side).lower()
    if "is_buyer_maker" in trade:
        return "sell" if trade["is_buyer_maker"] else "buy"
    if "maker" in trade:
        maker = trade["maker"]
        if isinstance(maker, str):
            maker = maker.lower()
            if maker in {"buyer", "buy"}:
                return "sell"
            if maker in {"seller", "sell"}:
                return "buy"
    return "neutral"


def compute_cvd(trades: Iterable[Dict]) -> float:
    """Compute cumulative volume delta from a list of trades."""

    delta = 0.0
    for trade in trades:
        qty = _extract_qty(trade)
        if qty <= 0:
            continue
        side = _extract_side(trade)
        if side.startswith("buy"):
            delta += qty
        elif side.startswith("sell"):
            delta -= qty
    return delta
