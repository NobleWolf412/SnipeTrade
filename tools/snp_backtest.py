#!/usr/bin/env python3
"""Offline backtest harness for the SnipeTrade scanner."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from snipetrade.exchanges import CcxtAdapter  # type: ignore  # pylint: disable=wrong-import-position
from snipetrade.scoring.confluence import ConfluenceScorer  # type: ignore  # pylint: disable=wrong-import-position
from snipetrade.output.telegram import TelegramNotifier  # type: ignore  # pylint: disable=wrong-import-position

SAMPLE_SYMBOLS: List[str] = ["BTC/USDT", "ETH/USDT"]
SAMPLE_TIMEFRAMES: List[str] = ["15m", "1h", "4h"]


def main() -> None:
    """Load cached OHLCV data, score sample symbols, and emit notifications."""

    adapter = CcxtAdapter(exchange="phemex")
    scorer = ConfluenceScorer(timeframes=SAMPLE_TIMEFRAMES)
    notifier = TelegramNotifier()

    setups = []
    for symbol in SAMPLE_SYMBOLS:
        setup = adapter.scan_symbol(symbol, SAMPLE_TIMEFRAMES, scorer)
        if setup:
            setups.append(setup)

    if not setups:
        print("[]")
        return

    payload = [setup.model_dump(mode="json", exclude_none=True) for setup in setups]
    print(json.dumps(payload, indent=2))

    for setup in setups:
        message = notifier.format_setup_message(setup)
        sanitized_message = "\n".join(line for line in message.splitlines() if line.strip())
        print("\nTelegram notification:")
        print(sanitized_message)


if __name__ == "__main__":
    main()
