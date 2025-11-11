#!/usr/bin/env python3
"""Generate weekly journal reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from snipetrade.analysis.report import build_report
from snipetrade.state.journal import JournalEntry


def main() -> None:
    parser = argparse.ArgumentParser(description="Weekly report generator")
    parser.add_argument("--journal", required=True, type=Path)
    parser.add_argument("--week", required=True)
    parser.add_argument("--markdown", required=True, type=Path)
    parser.add_argument("--csv", required=True, type=Path)
    args = parser.parse_args()

    with args.journal.open("r", encoding="utf-8") as handle:
        raw_entries = json.load(handle)

    entries = [
        JournalEntry(
            symbol=item["symbol"],
            timestamp=pd.to_datetime(item["timestamp"], utc=True),
            status=item["status"],
            reasons=item.get("reasons", []),
            score=float(item.get("score", 0.0)),
            filled=bool(item.get("filled", False)),
            outcome=item.get("outcome"),
            pnl=item.get("pnl"),
            extra=item.get("extra", {}),
        )
        for item in raw_entries
    ]

    report = build_report(entries, args.week)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    with args.markdown.open("w", encoding="utf-8") as handle:
        handle.write(report.to_markdown())
    report.to_csv(args.csv)


if __name__ == "__main__":
    import pandas as pd

    main()
