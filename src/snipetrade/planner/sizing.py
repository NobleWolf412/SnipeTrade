"""Leverage-aware position sizing."""

from __future__ import annotations

from typing import Any, Dict

from .leverage import estimate_liq_price, liq_is_safe, recommend_size_adjustment


def _round_qty(qty: float, lot_size: float) -> float:
    if lot_size <= 0:
        return qty
    steps = max(round(qty / lot_size), 1)
    return steps * lot_size


def _get_attr(cfg: Any, name: str, default: Any) -> Any:
    return getattr(cfg, name, default)


def position_size_leverage(entry: float, stop: float, side: str,
                           leverage: float, price: float,
                           risk_usd: float, lot_size: float,
                           min_notional: float,
                           maint_margin_rate: float,
                           atr: float,
                           cfg) -> Dict[str, Any]:
    """Compute leverage-aware position size with liquidation safety."""

    if entry <= 0 or price <= 0:
        raise ValueError("entry and price must be positive")
    if risk_usd <= 0:
        return {"qty": 0.0, "liq": 0.0, "reduced": False, "reason": "no risk budget"}

    distance = abs(entry - stop)
    if distance == 0:
        return {"qty": 0.0, "liq": 0.0, "reduced": False, "reason": "zero stop distance"}

    raw_qty = risk_usd / distance
    qty = max(raw_qty, 0.0)

    lot_size = max(lot_size, 0.0)
    if lot_size:
        qty = max(qty, lot_size)
    qty = _round_qty(qty, lot_size) if lot_size else qty

    notional = qty * price
    if notional < min_notional:
        qty = _round_qty(min_notional / price, lot_size) if lot_size else (min_notional / price)
        notional = qty * price

    effective_leverage = leverage
    liq = estimate_liq_price(entry, side, effective_leverage, maint_margin_rate)
    safe, reason = liq_is_safe(stop, liq, side, atr,
                               _get_attr(cfg, "LIQ_BUFFER_PCT", 0.0),
                               _get_attr(cfg, "LIQ_BUFFER_ATR_MULT", 0.0))

    reduced = False
    if not safe and _get_attr(cfg, "REDUCE_SIZE_IF_LIQ_TOO_CLOSE", False):
        factor, adj_reason = recommend_size_adjustment(
            entry, stop, side, leverage, maint_margin_rate, atr,
            _get_attr(cfg, "LIQ_BUFFER_PCT", 0.0),
            _get_attr(cfg, "LIQ_BUFFER_ATR_MULT", 0.0))
        if factor <= 0:
            if _get_attr(cfg, "SKIP_IF_AFTER_REDUCE_STILL_UNSAFE", False):
                return {"qty": 0.0, "liq": liq, "reduced": False, "reason": adj_reason}
        else:
            reduced = factor < 1.0
            qty *= factor
            effective_leverage = max(leverage * factor, 1.0)
            qty = _round_qty(qty, lot_size) if lot_size else qty
            notional = qty * price
            if notional < min_notional:
                if _get_attr(cfg, "SKIP_IF_AFTER_REDUCE_STILL_UNSAFE", False):
                    return {"qty": 0.0, "liq": liq, "reduced": reduced,
                            "reason": "qty below min notional after reduce"}
            liq = estimate_liq_price(entry, side, effective_leverage, maint_margin_rate)
            safe, reason = liq_is_safe(stop, liq, side, atr,
                                       _get_attr(cfg, "LIQ_BUFFER_PCT", 0.0),
                                       _get_attr(cfg, "LIQ_BUFFER_ATR_MULT", 0.0))
            if not safe and _get_attr(cfg, "SKIP_IF_AFTER_REDUCE_STILL_UNSAFE", False):
                return {"qty": 0.0, "liq": liq, "reduced": reduced, "reason": reason}

    return {"qty": qty, "liq": liq, "reduced": reduced, "reason": reason}
