"""Route trade plans through the autotrader pipeline."""

from __future__ import annotations

from typing import Any, Dict

from snipetrade.outputs.autotraders import executor, policy, reporter


async def route_autotrade(plan: Dict[str, Any], portfolio_state: Dict[str, Any], cfg, clocks) -> Dict[str, Any]:
    if not getattr(cfg, "AUTOTRADE_ENABLED", False):
        reporter.notify_status(plan, "ℹ️ Autotrade OFF (paper only)")
        return {"status": "disabled", "reason": "autotrade disabled"}

    allowed, reason = policy.check_policy(plan, portfolio_state, cfg)
    if not allowed:
        reporter.notify_status(plan, f"⛔ Autotrade blocked: {reason}")
        return {"status": "blocked", "reason": reason}

    result = await executor.execute_plan(plan, cfg, clocks)
    await reporter.record(result)
    return result


__all__ = ["route_autotrade"]
