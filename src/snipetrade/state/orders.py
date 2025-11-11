"""Persistent order state for deterministic replays."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

_STATE_PATH = Path("journal") / "orders_state.json"


def _load_state() -> Dict[str, Dict[str, object]]:
    if _STATE_PATH.exists():
        with open(_STATE_PATH, "r", encoding="utf-8") as handle:
            try:
                return json.load(handle)
            except json.JSONDecodeError:
                return {}
    return {}


def _save_state(state: Dict[str, Dict[str, object]]) -> None:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_STATE_PATH, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)


def save_intent(plan_id: str, payload: Dict[str, object]) -> None:
    state = _load_state()
    state[plan_id] = {
        "plan": payload,
        "status": "intent",
        "fills": [],
        "exchange_ids": {},
    }
    _save_state(state)


def update_status(plan_id: str, status: str, exchange_ids: Dict[str, str]) -> None:
    state = _load_state()
    entry = state.setdefault(plan_id, {"plan": {}, "fills": [], "exchange_ids": {}})
    entry["status"] = status
    entry.setdefault("exchange_ids", {}).update(exchange_ids)
    _save_state(state)


def append_fill(plan_id: str, fill: Dict[str, object]) -> None:
    state = _load_state()
    entry = state.setdefault(plan_id, {"plan": {}, "fills": [], "exchange_ids": {}})
    entry.setdefault("fills", []).append(fill)
    _save_state(state)


def load_open_orders() -> List[Dict[str, object]]:
    state = _load_state()
    open_orders = []
    for plan_id, entry in state.items():
        if entry.get("status") in {"filled", "canceled", "rejected"}:
            continue
        payload = dict(entry)
        payload["plan_id"] = plan_id
        open_orders.append(payload)
    return open_orders


__all__ = [
    "save_intent",
    "update_status",
    "append_fill",
    "load_open_orders",
]
