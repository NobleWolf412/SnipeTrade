"""Formatter for Telegram alerts including leverage and execution hints."""

from __future__ import annotations

from typing import Dict, List


def _format_reasons(reasons: List[str]) -> str:
    filtered = [r for r in reasons if r]
    return " | ".join(filtered[:5]) if filtered else "n/a"


def format_telegram_alert(payload: Dict) -> str:
    """Return a compact Telegram alert string."""

    symbol = payload.get("symbol", "UNKNOWN")
    timeframe = payload.get("timeframe", "?")
    direction = payload.get("direction", "?")
    score = payload.get("score", 0)

    entry_near = payload.get("entry_near")
    entry_far = payload.get("entry_far")
    stop = payload.get("stop")
    tp1 = payload.get("tp1")

    leverage = payload.get("leverage")
    qty = payload.get("qty")
    liq = payload.get("liq")
    liq_buffer = payload.get("liq_buffer")

    exec_hint = payload.get("execution", {})

    parts = [
        f"{symbol} {timeframe} {direction}",
        f"Score {score}",
        f"Entry N/F: {entry_near} / {entry_far}",
        f"SL {stop} | TP1 {tp1}",
        f"Lev {leverage}x | Qty {qty} | Liq {liq} ({liq_buffer})",
        f"RR {payload.get('rr')} | Dist {payload.get('distance_pct')}%",
        f"Spread {payload.get('spread_bps')}bps | Vol {payload.get('volume_usd_24h')}"
    ]

    reasons = _format_reasons(payload.get("reasons", []))
    parts.append(f"Reasons: {reasons}")

    if exec_hint:
        near = exec_hint.get("near_plan")
        fallback = exec_hint.get("fallback")
        plan_msg = []
        if near:
            mode = "LIMIT" if near.get("type") == "limit" else "STOP"
            post = " post-only" if near.get("post_only") else ""
            plan_msg.append(f"near: {mode}{post} @{near.get('price')}")
        if fallback:
            plan_msg.append(f"fallback → {fallback.get('type').upper()} @{fallback.get('price')} ({fallback.get('reason')})")
        far = exec_hint.get("far_plan")
        if far:
            mode = "LIMIT" if far.get("type") == "limit" else "STOP"
            plan_msg.append(f"far: {mode} @{far.get('price')}")
        if plan_msg:
            parts.append("Execution: " + "; ".join(plan_msg))

    links = payload.get("links", [])
    if links:
        parts.append("Links: " + " | ".join(links))

    return "\n".join(parts)
