"""Replay execution journal for deterministic audits."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List


def _load_records(path: Path) -> Iterable[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def _format_record(record: Dict[str, Any]) -> str:
    timestamp = record.get("timestamp")
    ts = timestamp
    try:
        ts = datetime.fromisoformat(timestamp).strftime("%H:%M:%S") if timestamp else "?"
    except ValueError:
        ts = timestamp
    event = record.get("event")
    if event:
        details = json.dumps(record.get("details", {}))
        return f"[{ts}] {record.get('symbol', '?')} {event}: {details}"
    result = record.get("result")
    if result:
        status = result.get("status")
        pnl = result.get("pnl")
        return f"[{ts}] RESULT {status} pnl={pnl}"
    return f"[{ts}] {json.dumps(record)}"


def replay(path: Path, symbol: str | None = None) -> List[str]:
    entries = []
    for record in _load_records(path):
        if symbol and record.get("symbol") not in {symbol, None}:
            res = record.get("result", {})
            if res.get("symbol") != symbol:
                continue
        entries.append(_format_record(record))
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay autotrade journal")
    parser.add_argument("--from", dest="journal", required=True, type=Path, help="Path to journal JSONL")
    parser.add_argument("--symbol", dest="symbol", type=str, default=None)
    args = parser.parse_args()

    lines = replay(args.journal, args.symbol)
    if not lines:
        print("No matching entries found")
        return
    for line in lines:
        print(line)


if __name__ == "__main__":
    main()
