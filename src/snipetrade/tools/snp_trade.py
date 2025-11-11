"""Utility to dry-run or execute a single plan."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict

from snipetrade import config as cfg_module
from snipetrade.outputs.autotraders import executor, policy, reporter
from snipetrade.runtime.router import route_autotrade
from snipetrade.state import orders as order_state


def _load_plan(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _portfolio_state() -> Dict[str, Any]:
    open_orders = order_state.load_open_orders()
    exposure_by_symbol: Dict[str, float] = {}
    for order in open_orders:
        plan = order.get("plan", {})
        symbol = plan.get("symbol")
        if not symbol:
            continue
        notional = plan.get("notional_usd") or plan.get("notional") or 0.0
        exposure_by_symbol[symbol] = exposure_by_symbol.get(symbol, 0.0) + float(notional)
    return {
        "open_trades": len(open_orders),
        "symbol_exposure": exposure_by_symbol,
        "total_exposure_usd": sum(exposure_by_symbol.values()),
        "daily_realized_loss_usd": 0.0,
    }


def _build_cfg(mode: str):
    attrs = {
        "AUTOTRADE_ENABLED": mode != "dry",
        "AUTOTRADE_MODE": mode,
        "MAX_CONCURRENT_TRADES": cfg_module.MAX_CONCURRENT_TRADES,
        "DAILY_RISK_USD_LIMIT": cfg_module.DAILY_RISK_USD_LIMIT,
        "PER_TRADE_RISK_USD": cfg_module.PER_TRADE_RISK_USD,
        "PER_SYMBOL_EXPOSURE_USD_MAX": cfg_module.PER_SYMBOL_EXPOSURE_USD_MAX,
        "TOTAL_EXPOSURE_USD_MAX": cfg_module.TOTAL_EXPOSURE_USD_MAX,
        "ALLOWLIST_SYMBOLS": cfg_module.ALLOWLIST_SYMBOLS,
        "TRADING_WINDOWS_UTC": cfg_module.TRADING_WINDOWS_UTC,
        "BLOCKLIST_DAYS": cfg_module.BLOCKLIST_DAYS,
        "POST_ONLY_DEFAULT": cfg_module.POST_ONLY_DEFAULT,
        "MAKER_TIMEOUT_SEC": cfg_module.MAKER_TIMEOUT_SEC,
        "AMEND_ON_DRIFT_BPS": cfg_module.AMEND_ON_DRIFT_BPS,
        "CANCEL_ON_TIMEOUT_SEC": cfg_module.CANCEL_ON_TIMEOUT_SEC,
        "RETRY_BACKOFF_MS": cfg_module.RETRY_BACKOFF_MS,
        "IDEMPOTENCY_PREFIX": cfg_module.IDEMPOTENCY_PREFIX,
    }
    return SimpleNamespace(**attrs)


async def _execute(plan: Dict[str, Any], cfg, mode: str) -> Dict[str, Any]:
    state = _portfolio_state()
    allowed, reason = policy.check_policy(plan, state, cfg)
    if not allowed:
        reporter.notify_status(plan, f"⛔ Policy blocked: {reason}")
        return {"status": "blocked", "reason": reason}
    if mode == "dry":
        reporter.notify_status(plan, "Dry-run completed — no orders placed")
        return {"status": "dry", "reason": "dry-run"}
    return await route_autotrade(plan, state, cfg, executor.Clocks())


def main() -> None:
    parser = argparse.ArgumentParser(description="Dry-run or execute a plan via the autotrader")
    parser.add_argument("--plan", required=True, type=Path, help="Path to plan JSON")
    parser.add_argument("--mode", choices=["dry", "paper", "live25", "live50", "live100"], default="dry")
    args = parser.parse_args()

    plan = _load_plan(args.plan)
    cfg = _build_cfg(args.mode)

    result = asyncio.run(_execute(plan, cfg, args.mode))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
