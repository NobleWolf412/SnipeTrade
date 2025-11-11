"""Helpers for constructing Phemex order payloads.

The builder normalises prices and quantities against the exchange constraints
so that higher level orchestration code can focus on intent rather than micro
structure differences between paper and live trading.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from typing import Dict, Optional


@dataclass(frozen=True)
class MarketConstraints:
    """Constraints reported by the exchange for a symbol.

    Attributes:
        price_tick: Smallest price increment allowed.
        quantity_step: Smallest quantity increment allowed.
        min_notional: Minimum notional (price * qty) required by the venue.
    """

    price_tick: Optional[float] = None
    quantity_step: Optional[float] = None
    min_notional: Optional[float] = None


def _round_to_step(value: float, step: Optional[float], *, rounding=ROUND_DOWN) -> float:
    """Round a floating point ``value`` to the provided ``step``.

    If ``step`` is ``None`` the value is returned unchanged. The function uses
    :class:`decimal.Decimal` for predictable rounding semantics.
    """

    if step in (None, 0):
        return float(value)

    quant = Decimal(str(step))
    decimal_value = Decimal(str(value))
    rounded = (decimal_value / quant).to_integral_value(rounding=rounding) * quant
    return float(rounded)


def _ensure_min_notional(qty: float, price: float, min_notional: Optional[float]) -> float:
    if not min_notional:
        return qty
    notional = qty * price
    if notional >= min_notional:
        return qty
    required_qty = Decimal(str(min_notional)) / Decimal(str(price))
    stepped_qty = _round_to_step(float(required_qty), None, rounding=ROUND_HALF_UP)
    return float(stepped_qty)


def build_limit_post_only(
    symbol: str,
    side: str,
    qty: float,
    price: float,
    reduce_only: bool = False,
    *,
    constraints: MarketConstraints | None = None,
) -> Dict[str, object]:
    """Construct a post-only limit order payload."""

    constraints = constraints or MarketConstraints()
    rounded_price = _round_to_step(price, constraints.price_tick, rounding=ROUND_DOWN)
    rounded_qty = _round_to_step(qty, constraints.quantity_step, rounding=ROUND_DOWN)
    rounded_qty = _ensure_min_notional(rounded_qty, rounded_price or price, constraints.min_notional)

    return {
        "symbol": symbol,
        "side": side.upper(),
        "type": "LIMIT",
        "price": rounded_price,
        "quantity": rounded_qty,
        "timeInForce": "PostOnly",
        "postOnly": True,
        "reduceOnly": bool(reduce_only),
    }


def build_stop_entry(
    symbol: str,
    side: str,
    qty: float,
    stop_price: float,
    *,
    constraints: MarketConstraints | None = None,
) -> Dict[str, object]:
    """Construct a stop-entry order payload."""

    constraints = constraints or MarketConstraints()
    rounded_stop = _round_to_step(stop_price, constraints.price_tick, rounding=ROUND_HALF_UP)
    rounded_qty = _round_to_step(qty, constraints.quantity_step, rounding=ROUND_DOWN)

    return {
        "symbol": symbol,
        "side": side.upper(),
        "type": "STOP",
        "stopPx": rounded_stop,
        "quantity": rounded_qty,
        "reduceOnly": False,
    }


def build_tp_limit(
    symbol: str,
    side: str,
    qty: float,
    price: float,
    reduce_only: bool = True,
    *,
    constraints: MarketConstraints | None = None,
) -> Dict[str, object]:
    """Construct a take-profit limit payload."""

    constraints = constraints or MarketConstraints()
    rounded_price = _round_to_step(price, constraints.price_tick, rounding=ROUND_HALF_UP)
    rounded_qty = _round_to_step(qty, constraints.quantity_step, rounding=ROUND_DOWN)

    return {
        "symbol": symbol,
        "side": side.upper(),
        "type": "LIMIT",
        "price": rounded_price,
        "quantity": rounded_qty,
        "reduceOnly": bool(reduce_only),
        "timeInForce": "GoodTillCancel",
    }


def build_sl_market(
    symbol: str,
    side: str,
    qty: float,
    stop_price: float,
    *,
    constraints: MarketConstraints | None = None,
) -> Dict[str, object]:
    """Construct a stop-loss market payload."""

    constraints = constraints or MarketConstraints()
    rounded_stop = _round_to_step(stop_price, constraints.price_tick, rounding=ROUND_HALF_UP)
    rounded_qty = _round_to_step(qty, constraints.quantity_step, rounding=ROUND_DOWN)

    return {
        "symbol": symbol,
        "side": side.upper(),
        "type": "STOP_MARKET",
        "stopPx": rounded_stop,
        "quantity": rounded_qty,
        "reduceOnly": True,
    }

__all__ = [
    "MarketConstraints",
    "build_limit_post_only",
    "build_stop_entry",
    "build_tp_limit",
    "build_sl_market",
]
