"""Execution planner for leverage-aware setups."""

from __future__ import annotations

from typing import Dict


def _timeout_ms(cfg) -> int:
    return int(getattr(cfg, "ENTRY_TIMEOUT_SEC", 60) * 1000)


def decide_execution(near: dict, far: dict, now_ts_ms: int, cfg) -> Dict:
    """Decide live execution hints."""

    timeout = _timeout_ms(cfg)
    fallback = None
    near_plan = {
        "type": near.get("type"),
        "price": near.get("price"),
        "post_only": near.get("post_only", False),
        "valid_until_ms": now_ts_ms + timeout if near.get("type") == "limit" else None,
        "reason": near.get("reason", "")
    }

    if near.get("type") == "limit":
        fallback = {
            "activate_after_ms": timeout,
            "type": "stop",
            "price": near.get("price"),
            "reason": "maker_timeout"
        }

    far_plan = {
        "type": far.get("type"),
        "price": far.get("price"),
        "post_only": far.get("post_only", False),
        "reason": far.get("reason", "")
    }

    if far.get("type") == "limit" and near.get("type") != "limit" and fallback:
        # ensure far remains passive, but note fallback takeover
        far_plan["valid_until_ms"] = now_ts_ms + timeout

    return {
        "near_plan": near_plan,
        "far_plan": far_plan,
        "fallback": fallback
    }
