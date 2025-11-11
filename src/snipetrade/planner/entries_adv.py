"""Advanced entry planner anchored on structure and order-flow."""

from __future__ import annotations

from typing import Dict, Literal

Side = Literal["LONG", "SHORT"]


class _CfgProxy:
    def __init__(self, cfg):
        self._cfg = cfg

    def get(self, name: str, default):
        return getattr(self._cfg, name, default)


def _round(price: float, tick: float) -> float:
    if tick <= 0:
        return price
    steps = round(price / tick)
    return steps * tick


def _atr_guard(entry: float, stop: float, atr: float, min_frac: float) -> bool:
    if atr <= 0:
        return True
    return abs(entry - stop) >= atr * min_frac


def _apply_session_bias(price: float, side: Side, session: str, bias_enabled: bool) -> float:
    if not bias_enabled:
        return price
    session = (session or "").lower()
    if session in {"london", "new_york", "ny"}:
        # tighten toward current price by 1%
        adjust = 0.01
    elif session in {"asia", "asian"}:
        adjust = -0.01
    else:
        return price
    if side == "LONG":
        return price * (1 - adjust)
    return price * (1 + adjust)


def _maker_allowed(orderflow_ctx: Dict, cfg: _CfgProxy) -> bool:
    return (orderflow_ctx.get("obi", 0.0) >= cfg.get("OBI_MAKER_THRESHOLD", 0.0)
            and orderflow_ctx.get("spread_bps", 0.0) <= cfg.get("MAKER_SPREAD_MAX_BPS", 10.0))


def _stop_bias(price: float, tick: float, side: Side, ticks: int) -> float:
    if tick <= 0:
        return price
    offset = tick * max(ticks, 0)
    if side == "LONG":
        return price + offset
    return price - offset


def propose_entries_adv(
    setup: Dict,
    price_ctx: Dict,
    orderflow_ctx: Dict,
    structure_ctx: Dict,
    vwap_ctx: Dict,
    cfg
) -> Dict:
    """Return near/far entries combining structure, VWAP and order-flow."""

    side: Side = setup.get("direction", "LONG")  # default long for safety
    tick = price_ctx.get("tick_size", 0.0) or 0.0
    atr = setup.get("atr", 0.0)
    stop = setup.get("stop")
    proxy = _CfgProxy(cfg)

    vwap = vwap_ctx.get("vwap", price_ctx.get("price"))
    std = vwap_ctx.get("std", 0.0)
    k_std = proxy.get("VWAP_K_STD", 0.0)
    bias = vwap - k_std * std if side == "LONG" else vwap + k_std * std

    ob_mid = structure_ctx.get("ob_mid", price_ctx.get("price"))
    ob_edge = structure_ctx.get("ob_low" if side == "LONG" else "ob_high", ob_mid)
    fvg = structure_ctx.get("fvg_lo" if side == "LONG" else "fvg_hi", ob_edge)

    near_price = (ob_mid + bias) / 2.0
    far_price = (ob_edge + fvg) / 2.0

    session_bias = proxy.get("SESSION_BIAS", {}).get("london_ny_tighter", False)
    near_price = _apply_session_bias(near_price, side, price_ctx.get("session"), session_bias)
    far_price = _apply_session_bias(far_price, side, price_ctx.get("session"), session_bias)

    maker_allowed = _maker_allowed(orderflow_ctx, proxy)
    liq_cluster = orderflow_ctx.get("liq_in_zone", False)

    near_type = "limit" if maker_allowed and not liq_cluster else "stop"
    far_type = "limit" if maker_allowed else "stop"

    if near_type == "limit":
        queue_ticks = proxy.get("QUEUE_OFFSET_TICKS", 0)
        offset = tick * max(queue_ticks, 0)
        if side == "LONG":
            near_price = min(near_price, price_ctx.get("price", near_price)) - offset
        else:
            near_price = max(near_price, price_ctx.get("price", near_price)) + offset
    else:
        near_price = _stop_bias(near_price, tick, side, proxy.get("STOP_ENTRY_TICKS", 1))

    if far_type == "limit":
        offset = tick * max(proxy.get("QUEUE_OFFSET_TICKS", 0), 0)
        if side == "LONG":
            far_price = min(far_price, near_price) - offset
        else:
            far_price = max(far_price, near_price) + offset
    else:
        far_price = _stop_bias(far_price, tick, side, proxy.get("STOP_ENTRY_TICKS", 1))

    near_price = _round(near_price, tick)
    far_price = _round(far_price, tick)

    if stop is not None and atr:
        if not _atr_guard(near_price, stop, atr, proxy.get("ENTRY_ATR_MIN_FRAC", 0.0)):
            raise ValueError("Near entry violates ATR guard")
        if not _atr_guard(far_price, stop, atr, proxy.get("ENTRY_ATR_MIN_FRAC", 0.0)):
            raise ValueError("Far entry violates ATR guard")

    near = {
        "price": near_price,
        "type": near_type,
        "post_only": near_type == "limit",
        "reason": "OB anchored with orderflow" if maker_allowed else "liquidity stop"
    }

    far = {
        "price": far_price,
        "type": far_type,
        "post_only": far_type == "limit",
        "reason": "FVG extension" if maker_allowed else "protective stop"
    }

    return {"near": near, "far": far}
