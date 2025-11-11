"""Telegram output helper for batch mode."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from . import formatter

MAX_MESSAGE_LENGTH = 4096


def _get_cfg_value(cfg: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in cfg:
            return cfg[key]
    return default


def _escape_markdown(value: str) -> str:
    from re import sub

    return sub(r"([_\*\[\]()~`>#+\-=|{}.!])", r"\\\1", value)


def _chunk_message(text: str, limit: int = MAX_MESSAGE_LENGTH) -> List[str]:
    if len(text) <= limit:
        return [text]
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + limit, len(text))
        chunks.append(text[start:end])
        start = end
    return chunks


def send_summary_top_n(bot: Any, chat_id: str, scan_meta: Dict[str, Any], results: List[Dict[str, Any]]) -> str:
    summary_text = formatter.to_telegram_summary(results[:10])
    escaped = _escape_markdown(summary_text)
    bot.send_message(chat_id=chat_id, text=escaped, parse_mode="MarkdownV2")
    return escaped


def send_setup_detail(bot: Any, chat_id: str, setup: Dict[str, Any]) -> List[str]:
    detail_text = formatter.to_telegram_detail(setup)
    messages = []
    for chunk in _chunk_message(detail_text):
        bot.send_message(chat_id=chat_id, text=chunk, parse_mode="MarkdownV2")
        messages.append(chunk)
    return messages


def _build_footer(scan_meta: Dict[str, Any]) -> str:
    filters = scan_meta.get("filters", {})
    components = [
        f"Scan {scan_meta.get('scan_id')}",
        f"Min score {filters.get('min_score')}",
        f"Limit {filters.get('limit')}",
    ]
    if filters.get("symbols"):
        components.append(f"Symbols: {', '.join(filters['symbols'][:5])}")
    return " \n".join(components)


def send_batch_top_setups(
    scan_meta: Dict[str, Any],
    results: List[Dict[str, Any]],
    cfg: Dict[str, Any],
    *,
    bot: Optional[Any] = None,
) -> List[str]:
    if not _get_cfg_value(cfg, "TELEGRAM_ENABLED", "telegram_enabled", default=True):
        return []

    chat_id = _get_cfg_value(cfg, "TELEGRAM_CHAT_ID", "telegram_chat_id")
    token = _get_cfg_value(cfg, "TELEGRAM_BOT_TOKEN", "telegram_bot_token")
    if bot is None:
        if not token or not chat_id:
            return []
        from telegram import Bot  # type: ignore

        bot = Bot(token=token)
    elif not chat_id:
        raise ValueError("chat_id must be provided when bot instance is injected")

    rate_delay = _get_cfg_value(cfg, "TELEGRAM_RATE_MS", "telegram_rate_ms", default=400) / 1000.0
    max_msgs = int(_get_cfg_value(cfg, "TELEGRAM_MAX_MSGS", "telegram_max_msgs", default=12))
    include_summary = bool(_get_cfg_value(cfg, "TELEGRAM_BATCH_SUMMARY", "telegram_batch_summary", default=True))

    sent_messages: List[str] = []
    remaining_slots = max_msgs

    if include_summary and remaining_slots > 0:
        summary_text = send_summary_top_n(bot, chat_id, scan_meta, results)
        sent_messages.append(summary_text)
        remaining_slots -= 1
        if rate_delay > 0:
            time.sleep(rate_delay)

    detail_capacity = max(0, remaining_slots - 1)
    for setup in results:
        if detail_capacity <= 0:
            break
        detail_chunks = send_setup_detail(bot, chat_id, setup)
        for chunk in detail_chunks:
            sent_messages.append(chunk)
            detail_capacity -= 1
            remaining_slots -= 1
            if detail_capacity <= 0:
                break
            if rate_delay > 0:
                time.sleep(rate_delay)

    if remaining_slots > 0:
        footer_text = _escape_markdown(_build_footer(scan_meta))
        bot.send_message(chat_id=chat_id, text=footer_text, parse_mode="MarkdownV2")
        sent_messages.append(footer_text)

    return sent_messages
