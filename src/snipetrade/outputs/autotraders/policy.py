"""Autotrade guardrails and routing policy."""

from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Dict, Tuple


def _parse_window(window: str) -> Tuple[time, time]:
    start_str, end_str = window.split("-")
    start_hour, start_minute = [int(part) for part in start_str.split(":")]
    end_hour, end_minute = [int(part) for part in end_str.split(":")]
    return time(start_hour, start_minute, tzinfo=timezone.utc), time(end_hour, end_minute, tzinfo=timezone.utc)


def _within_trading_window(now: datetime, windows) -> bool:
    if not windows:
        return True
    current_time = now.timetz()
    for window in windows:
        start, end = _parse_window(window)
        if start <= end:
            if start <= current_time <= end:
                return True
        else:  # overnight window
            if current_time >= start or current_time <= end:
                return True
    return False


def _extract_notional(plan: Dict[str, object]) -> float:
    notional_keys = [
        "notional_usd",
        "notional",
        "exposure_usd",
        "planned_notional",
    ]
    for key in notional_keys:
        value = plan.get(key)
        if value:
            return float(value)

    entry_price = None
    if isinstance(plan.get("entry_plan"), (list, tuple)) and plan["entry_plan"]:
        entry_price = float(plan["entry_plan"][0])
    price = float(plan.get("entry_price", entry_price or 0) or 0)
    qty = float(plan.get("quantity") or plan.get("qty") or plan.get("size", 0))
    if price and qty:
        return price * qty
    return 0.0


def _extract_risk(plan: Dict[str, object]) -> float:
    for key in ("risk_usd", "planned_risk_usd", "risk"):
        value = plan.get(key)
        if value:
            return float(value)
    return 0.0


def check_policy(plan: Dict[str, object], portfolio_state: Dict[str, object], cfg) -> Tuple[bool, str]:
    """Return (allowed, reason). Evaluates exposure, daily loss, windows, allowlist."""

    if not getattr(cfg, "AUTOTRADE_ENABLED", False):
        return False, "autotrade disabled"

    mode = getattr(cfg, "AUTOTRADE_MODE", "paper")
    if mode not in {"paper", "live25", "live50", "live100"}:
        return False, f"unsupported mode {mode}"

    symbol = str(plan.get("symbol")) if plan.get("symbol") else None
    if not symbol:
        return False, "plan missing symbol"

    allowlist = getattr(cfg, "ALLOWLIST_SYMBOLS", [])
    if allowlist and symbol not in allowlist:
        return False, f"symbol {symbol} not allowlisted"

    today = datetime.now(timezone.utc).date().isoformat()
    if today in getattr(cfg, "BLOCKLIST_DAYS", []):
        return False, f"{today} blocked"

    if not _within_trading_window(datetime.now(timezone.utc), getattr(cfg, "TRADING_WINDOWS_UTC", [])):
        return False, "outside trading window"

    daily_loss = portfolio_state.get("daily_realized_loss_usd") or portfolio_state.get("daily_realized_loss") or 0.0
    daily_limit = getattr(cfg, "DAILY_RISK_USD_LIMIT", 0)
    if daily_limit and abs(float(daily_loss)) >= daily_limit:
        return False, "daily loss limit reached"

    open_trades = portfolio_state.get("open_trades") or portfolio_state.get("open_positions") or 0
    if getattr(cfg, "MAX_CONCURRENT_TRADES", 0) and open_trades >= cfg.MAX_CONCURRENT_TRADES:
        return False, "max concurrent trades reached"

    notional = _extract_notional(plan)
    if notional <= 0:
        return False, "plan has zero notional"

    symbol_exposure = portfolio_state.get("symbol_exposure", {}).get(symbol, 0.0)
    if getattr(cfg, "PER_SYMBOL_EXPOSURE_USD_MAX", 0) and symbol_exposure + notional > cfg.PER_SYMBOL_EXPOSURE_USD_MAX:
        return False, f"symbol exposure {symbol_exposure + notional:.2f} > limit"

    total_exposure = portfolio_state.get("total_exposure_usd") or portfolio_state.get("total_exposure") or 0.0
    if getattr(cfg, "TOTAL_EXPOSURE_USD_MAX", 0) and total_exposure + notional > cfg.TOTAL_EXPOSURE_USD_MAX:
        return False, "total exposure limit reached"

    trade_risk = _extract_risk(plan) or notional * 0.02
    if getattr(cfg, "PER_TRADE_RISK_USD", 0) and trade_risk > cfg.PER_TRADE_RISK_USD:
        return False, f"per-trade risk {trade_risk:.2f} exceeds {cfg.PER_TRADE_RISK_USD}"

    return True, "ok"


__all__ = ["check_policy"]
