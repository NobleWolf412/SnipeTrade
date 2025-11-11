"""Reporting utilities for autotrade execution."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from snipetrade import config as cfg_module
from snipetrade.config import Config
from snipetrade.output.telegram import TelegramNotifier
from snipetrade.runtime.metrics import metrics

_JOURNAL_DIR = Path("journal")
_notifier: Optional[TelegramNotifier] = None


def _redact(payload: Dict[str, object]) -> Dict[str, object]:
    if not getattr(cfg_module, "LOG_REDACT_KEYS", False):
        return payload
    redacted = {}
    for key, value in payload.items():
        if "key" in key.lower() or "secret" in key.lower():
            redacted[key] = "***"
        else:
            redacted[key] = value
    return redacted


def _ensure_notifier() -> Optional[TelegramNotifier]:
    global _notifier
    if _notifier is not None:
        return _notifier

    config = Config()
    if config.has_telegram_configured():
        _notifier = TelegramNotifier(
            config.get("telegram_bot_token"),
            config.get("telegram_chat_id"),
        )
    else:
        _notifier = None
    return _notifier


def _journal_path() -> Path:
    _JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    filename = datetime.utcnow().strftime("%Y-%m-%d") + ".jsonl"
    return _JOURNAL_DIR / filename


def _append_journal(record: Dict[str, object]) -> None:
    path = _journal_path()
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(_redact(record)) + "\n")


def notify_status(plan: Dict[str, object], message: str) -> None:
    symbol = plan.get("symbol", "UNKNOWN")
    direction = plan.get("direction") or plan.get("side", "?")
    qty = plan.get("quantity") or plan.get("qty") or plan.get("size") or 0
    entry_price = None
    if isinstance(plan.get("entry_plan"), (list, tuple)) and plan["entry_plan"]:
        entry_price = plan["entry_plan"][0]
    entry_price = plan.get("entry_price", entry_price)
    header = f"{symbol} {direction} qty={qty} entry={entry_price}".strip()
    full_message = f"{header} — {message}".replace("  ", " ")
    print(full_message)
    notifier = _ensure_notifier()
    if notifier:
        notifier.send_message(full_message)


async def record(result: Dict[str, object]) -> None:
    await metrics.incr("orders_recorded")
    record_payload = {
        "timestamp": datetime.utcnow().isoformat(),
        "result": result,
    }
    _append_journal(record_payload)


def log_event(plan: Dict[str, object], event: str, details: Dict[str, object]) -> None:
    payload = {
        "timestamp": datetime.utcnow().isoformat(),
        "plan_id": plan.get("id") or plan.get("plan_id"),
        "symbol": plan.get("symbol"),
        "event": event,
        "details": details,
    }
    _append_journal(payload)


__all__ = ["notify_status", "record", "log_event"]
