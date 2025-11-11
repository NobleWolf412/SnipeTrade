"""Lightweight simulator for leverage-aware trade plans."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional


@dataclass
class PricePoint:
    ts: int
    price: float


class SimulationEngine:
    """Backtest fills with maker/stop semantics and leverage costs."""

    def __init__(self, maker_fee_bps: float, taker_fee_bps: float, slippage_bps: float):
        self.maker_fee = maker_fee_bps / 10_000
        self.taker_fee = taker_fee_bps / 10_000
        self.slippage = slippage_bps / 10_000

    def _should_fill_limit(self, side: str, price: float, level: float) -> bool:
        return price <= level if side == "LONG" else price >= level

    def _should_trigger_stop(self, side: str, price: float, level: float) -> bool:
        return price >= level if side == "LONG" else price <= level

    def _apply_slippage(self, side: str, price: float, level: float) -> float:
        move = level * self.slippage
        return level + move if side == "LONG" else level - move

    def run(self, plan: Dict, prices: Iterable[Dict]) -> Dict:
        side = plan.get("side", "LONG")
        qty = plan.get("qty", 0.0)
        near = plan.get("entries", {}).get("near", {})
        fallback = plan.get("execution", {}).get("fallback")
        start_ts: Optional[int] = None
        fill = None
        fill_type = None

        price_points: List[PricePoint] = []
        for point in prices:
            price_points.append(PricePoint(ts=int(point["ts"]), price=float(point["price"])))

        for point in price_points:
            if start_ts is None:
                start_ts = point.ts
            if near.get("type") == "limit" and fill is None:
                if self._should_fill_limit(side, point.price, near.get("price")):
                    fill = near.get("price")
                    fill_type = "maker"
                    break
                if fallback and (point.ts - start_ts) >= fallback.get("activate_after_ms", 0):
                    if self._should_trigger_stop(side, point.price, fallback.get("price")):
                        fill = self._apply_slippage(side, point.price, fallback.get("price"))
                        fill_type = "fallback"
                        break
            else:
                if self._should_trigger_stop(side, point.price, near.get("price")):
                    fill = self._apply_slippage(side, point.price, near.get("price"))
                    fill_type = "taker"
                    break

        if fill is None:
            return {"filled": False, "pnl": 0.0, "fees": 0.0}

        fee_rate = self.maker_fee if fill_type == "maker" else self.taker_fee
        notional = qty * fill
        fees = notional * fee_rate

        stop = plan.get("stop")
        tp = plan.get("tps", [])
        exit_price = stop
        exit_type = "stop"
        for point in price_points:
            if point.price <= stop if side == "LONG" else point.price >= stop:
                exit_price = stop
                exit_type = "stop"
                break
            for target in tp:
                if side == "LONG" and point.price >= target:
                    exit_price = target
                    exit_type = "tp"
                    stop = fill  # breakeven after TP1
                    break
                if side == "SHORT" and point.price <= target:
                    exit_price = target
                    exit_type = "tp"
                    stop = fill
                    break
            if exit_type == "tp":
                break

        pnl = (exit_price - fill) * qty if side == "LONG" else (fill - exit_price) * qty
        pnl -= fees

        return {
            "filled": True,
            "fill_type": fill_type,
            "fill_price": fill,
            "exit_price": exit_price,
            "exit_type": exit_type,
            "fees": fees,
            "pnl": pnl
        }
