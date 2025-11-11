#!/usr/bin/env python3
"""CLI entrypoint for walk-forward backtests."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict

import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from snipetrade.sim.engine import BacktestEngine

from tools._snp_utils import load_data, load_profile


def main() -> None:
    parser = argparse.ArgumentParser(description="Walk-forward simulation")
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--csv", type=Path, help="Optional CSV with OHLCV data")
    parser.add_argument("--train", default="30d")
    parser.add_argument("--test", default="14d")
    parser.add_argument("--steps", type=int, default=3)
    args = parser.parse_args()

    frame = load_data(args.csv)
    profile = load_profile(args.profile)
    engine = BacktestEngine()
    result = engine.run_walk_forward(frame, profile, train=args.train, test=args.test, steps=args.steps)

    payload: Dict[str, Any] = {
        "combined": {k: (1e6 if isinstance(v, float) and math.isinf(v) else v) for k, v in result.combined_metrics.items()},
        "iterations": [],
    }
    for iteration in result.iterations:
        trades = iteration.trades
        payload["iterations"].append(
            {
                "train": {
                    "start": iteration.train_window.start.isoformat(),
                    "end": iteration.train_window.end.isoformat(),
                },
                "test": {
                    "start": iteration.test_window.start.isoformat(),
                    "end": iteration.test_window.end.isoformat(),
                },
                "metrics": {k: (1e6 if isinstance(v, float) and math.isinf(v) else v) for k, v in iteration.metrics.items()},
                "trades": [trade.spec.metadata for trade in trades],
            }
        )

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


if __name__ == "__main__":
    main()
