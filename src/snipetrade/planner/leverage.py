"""Leverage helpers and liquidation safety checks."""

from __future__ import annotations

from typing import Literal, Tuple

Side = Literal["LONG", "SHORT"]


def estimate_liq_price(entry: float, side: Side, leverage: float,
                       maint_margin_rate: float) -> float:
    """Approximate isolated-liq price for USDT-margined perp; exchange-agnostic."""

    if leverage <= 0:
        raise ValueError("leverage must be positive")
    if entry <= 0:
        raise ValueError("entry price must be positive")

    mmr = max(maint_margin_rate, 0.0)
    lev = max(leverage, 1e-9)

    if side == "LONG":
        return entry * (1 - 1 / lev + mmr)
    if side == "SHORT":
        return entry * (1 + 1 / lev - mmr)
    raise ValueError(f"Unsupported side: {side}")


def _buffers(sl: float, side: Side, atr: float, liq_buffer_pct: float,
             liq_buffer_atr_mult: float) -> Tuple[float, float]:
    pct_buffer = abs(sl) * (liq_buffer_pct / 100.0)
    atr_buffer = max(atr, 0.0) * liq_buffer_atr_mult
    return pct_buffer, atr_buffer


def liq_is_safe(sl: float, liq: float, side: Side,
                atr: float, liq_buffer_pct: float, liq_buffer_atr_mult: float) -> Tuple[bool, str]:
    """True if liq is safely beyond SL by pct and ATR buffers; include reason."""

    pct_buffer, atr_buffer = _buffers(sl, side, atr, liq_buffer_pct, liq_buffer_atr_mult)
    min_gap = max(pct_buffer, atr_buffer)

    if side == "LONG":
        gap = sl - liq
        if liq >= sl:
            return False, "liq above stop"
        if gap >= min_gap:
            return True, "liq safely below stop"
        return False, f"need {min_gap:.4f} gap, have {gap:.4f}"

    if side == "SHORT":
        gap = liq - sl
        if liq <= sl:
            return False, "liq below stop"
        if gap >= min_gap:
            return True, "liq safely above stop"
        return False, f"need {min_gap:.4f} gap, have {gap:.4f}"

    raise ValueError(f"Unsupported side: {side}")


def recommend_size_adjustment(entry: float, sl: float, side: Side,
                              leverage: float, maint_margin_rate: float,
                              atr: float, liq_buffer_pct: float,
                              liq_buffer_atr_mult: float) -> Tuple[float, str]:
    """Return factor ∈ (0,1] to shrink size so liq clears buffers; 0.0 if impossible."""

    if leverage <= 0:
        return 0.0, "invalid leverage"

    pct_buffer, atr_buffer = _buffers(sl, side, atr, liq_buffer_pct, liq_buffer_atr_mult)
    min_gap = max(pct_buffer, atr_buffer)

    target_sl = sl
    if side == "LONG":
        required = target_sl - min_gap
        if required <= 0:
            required = target_sl * (1 - 1e-6)
        rhs = 1 + maint_margin_rate - required / entry
    else:  # SHORT
        required = target_sl + min_gap
        rhs = required / entry + maint_margin_rate - 1

    if rhs <= 0:
        return 1.0, "any leverage safe"

    max_safe_leverage = 1.0 / rhs
    if max_safe_leverage <= 0:
        return 0.0, "no leverage satisfies buffers"

    if max_safe_leverage >= leverage:
        return 1.0, "current leverage safe"

    factor = max_safe_leverage / leverage
    if factor < 1e-3:
        return 0.0, "reduction insufficient"

    return factor, f"reduce leverage to {max_safe_leverage:.2f}x"
