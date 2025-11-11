"""Generate weekly digest and push to Telegram."""

from __future__ import annotations

import os
from pathlib import Path

import requests

from analysis.live_metrics import LiveMetricsStore
from analysis.report_html import WeeklyReport


def _telegram_token() -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not configured")
    return token


def _telegram_chat() -> str:
    chat = os.getenv("TELEGRAM_CHAT_ID")
    if not chat:
        raise RuntimeError("TELEGRAM_CHAT_ID not configured")
    return chat


def push_digest(metrics_db: Path, output_dir: Path) -> Path:
    store = LiveMetricsStore(metrics_db)
    report = WeeklyReport(store)
    report_path = report.render(output_dir / "weekly_report.html")
    df = store.fetch_recent(limit=1000)
    summary = df.tail(1).to_dict("records")[0]
    message = (
        "SnipeTrade Weekly Digest\n"
        f"Equity: {summary['equity']:.2f}\n"
        f"Drawdown: {summary['drawdown_pct']:.2f}%\n"
        f"Profit Factor: {summary['profit_factor']:.2f}\n"
        f"Win Rate: {summary['win_rate']:.2%}"
    )
    token = _telegram_token()
    chat_id = _telegram_chat()
    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": message},
        timeout=10,
    )
    resp.raise_for_status()
    return report_path


if __name__ == "__main__":
    metrics_db = Path("data/metrics.sqlite")
    output_dir = Path("data/reports")
    push_digest(metrics_db, output_dir)
