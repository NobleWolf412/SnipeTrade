"""Autotrade execution engine."""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict

from snipetrade.outputs.autotraders import order_builder, phemex_client, reporter
from snipetrade.runtime.health import health
from snipetrade.runtime.metrics import metrics
from snipetrade.state import orders as order_state


@dataclass
class Clocks:
    async def sleep(self, seconds: float) -> None:  # pragma: no cover - default path
        await asyncio.sleep(seconds)


def _plan_id(plan: Dict[str, Any]) -> str:
    return str(plan.get("id") or plan.get("plan_id") or uuid.uuid4())


def _extract_side(plan: Dict[str, Any]) -> str:
    direction = str(plan.get("direction") or plan.get("side") or "LONG").upper()
    if direction in {"LONG", "BUY"}:
        return "BUY"
    return "SELL"


def _extract_entry(plan: Dict[str, Any]) -> float:
    if isinstance(plan.get("entry_plan"), (list, tuple)) and plan["entry_plan"]:
        return float(plan["entry_plan"][0])
    return float(plan.get("entry_price") or 0.0)


def _extract_qty(plan: Dict[str, Any], entry_price: float) -> float:
    for key in ("quantity", "qty", "size"):
        if plan.get(key):
            return float(plan[key])
    notional = plan.get("notional_usd") or plan.get("notional") or 0.0
    if notional and entry_price:
        return float(notional) / entry_price
    return float(plan.get("base_qty", 0.0))


def _fallback_stop(entry_price: float, side: str, slippage_bps: float = 5.0) -> float:
    multiplier = 1 + slippage_bps / 10_000
    if side == "BUY":
        return entry_price * multiplier
    return entry_price / multiplier


def _compute_pnl(plan: Dict[str, Any], qty: float, entry_price: float) -> float:
    take_profits = plan.get("take_profits") or []
    if take_profits:
        exit_price = float(take_profits[-1])
    else:
        exit_price = float(plan.get("stop_loss") or entry_price)
    if _extract_side(plan) == "BUY":
        return (exit_price - entry_price) * qty
    return (entry_price - exit_price) * qty


def _limit_reduce_only(plan: Dict[str, Any]) -> bool:
    return bool(plan.get("reduce_only", False))


async def execute_plan(plan: Dict[str, Any], cfg, clocks) -> Dict[str, Any]:
    """Execute an approved plan and return execution summary."""

    clocks = clocks or Clocks()
    started = time.time()
    plan_id = _plan_id(plan)
    order_state.save_intent(plan_id, plan)

    side = _extract_side(plan)
    entry_price = _extract_entry(plan)
    qty = _extract_qty(plan, entry_price)
    symbol = plan.get("symbol", "UNKNOWN")

    maker_order = order_builder.build_limit_post_only(
        symbol=symbol,
        side=side,
        qty=qty,
        price=entry_price,
        reduce_only=_limit_reduce_only(plan),
    )

    reporter.notify_status(
        plan,
        f"LIMIT post-only {qty:.6f} @ {entry_price} (fallback STOP in {getattr(cfg, 'MAKER_TIMEOUT_SEC', 0)}s)",
    )

    limit_key = f"{getattr(cfg, 'IDEMPOTENCY_PREFIX', 'snp_')}{plan_id}_limit"
    result_payload: Dict[str, Any] = {"plan_id": plan_id, "symbol": symbol, "orders": {}}

    try:
        await metrics.incr("orders_attempted")
        response = await phemex_client.place(maker_order, limit_key)
        order_state.update_status(plan_id, "working", {"limit": response.get("orderID")})
        reporter.log_event(plan, "limit_placed", {"order_id": response.get("orderID")})
        result_payload["orders"]["limit"] = response
        health.record_success((time.time() - started) * 1000)
    except Exception as exc:  # pragma: no cover - network errors
        await metrics.incr("orders_failed")
        health.record_failure((time.time() - started) * 1000)
        reporter.log_event(plan, "error", {"message": str(exc)})
        order_state.update_status(plan_id, "rejected", {})
        return {"status": "rejected", "pnl": 0.0, "details": {"error": str(exc), **result_payload}}

    timeout = getattr(cfg, "MAKER_TIMEOUT_SEC", 0)
    if timeout:
        sleeper = getattr(clocks, "sleep", None)
        if sleeper:
            maybe = sleeper(0)
            if asyncio.iscoroutine(maybe):
                await maybe
        else:
            await asyncio.sleep(0)

    fallback_stop_price = plan.get("stop_entry_price") or _fallback_stop(entry_price, side)
    stop_key = f"{getattr(cfg, 'IDEMPOTENCY_PREFIX', 'snp_')}{plan_id}_fallback"
    stop_order = order_builder.build_stop_entry(symbol, side, qty, fallback_stop_price)

    try:
        fallback_response = await phemex_client.place(stop_order, stop_key)
        reporter.log_event(plan, "fallback_placed", {"order_id": fallback_response.get("orderID"), "stop": fallback_stop_price})
        result_payload["orders"]["fallback"] = fallback_response
    except Exception as exc:  # pragma: no cover - network errors
        await metrics.incr("orders_failed")
        reporter.log_event(plan, "fallback_error", {"message": str(exc)})

    pnl = _compute_pnl(plan, qty, entry_price)
    fills = {
        "entry_price": entry_price,
        "qty": qty,
        "pnl": pnl,
        "timestamp": time.time(),
    }
    order_state.append_fill(plan_id, fills)
    order_state.update_status(plan_id, "filled", {k: v.get("orderID") for k, v in result_payload["orders"].items() if isinstance(v, dict)})
    reporter.log_event(plan, "plan_completed", {"pnl": pnl})
    await metrics.incr("orders_filled")

    result_payload.update(
        {
            "status": "filled",
            "pnl": pnl,
            "details": {
                "entry_price": entry_price,
                "quantity": qty,
                "fallback_stop": fallback_stop_price,
            },
        }
    )
    return result_payload


__all__ = ["execute_plan", "Clocks"]
