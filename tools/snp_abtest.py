#!/usr/bin/env python3
"""Profile A/B comparison CLI."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Dict

import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from snipetrade.profiles.abtest import ProfileResult, run_ab_test
from snipetrade.sim.engine import BacktestEngine

from tools._snp_utils import load_data, load_profile


def parse_condition(expression: str, metrics: Dict[str, float]) -> bool:
    mapping = {"PF": "profit_factor", "MaxDD": "max_drawdown", "ExpR": "expectancy"}
    clauses = [clause.strip() for clause in expression.split("&&")]
    for clause in clauses:
        if not clause:
            continue
        for symbol, key in mapping.items():
            if clause.startswith(symbol):
                rest = clause[len(symbol) :]
                break
        else:
            raise ValueError(f"Unknown metric in clause: {clause}")
        if rest.startswith(">="):
            op = ">="
            value = float(rest[2:].strip())
            if metrics.get(key, 0.0) < value:
                return False
        elif rest.startswith("<="):
            op = "<="
            value = float(rest[2:].strip())
            if metrics.get(key, 0.0) > value:
                return False
        else:
            raise ValueError(f"Unsupported operator in clause: {clause}")
    return True


def decide_winner(a: ProfileResult, b: ProfileResult) -> ProfileResult:
    if b.metrics["profit_factor"] > a.metrics["profit_factor"]:
        return b
    if b.metrics["profit_factor"] == a.metrics["profit_factor"]:
        if b.metrics.get("max_drawdown", 0) < a.metrics.get("max_drawdown", 0):
            return b
    return a


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile A/B testing")
    parser.add_argument("--profileA", required=True, type=Path)
    parser.add_argument("--profileB", required=True, type=Path)
    parser.add_argument("--default", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--train", default="30d")
    parser.add_argument("--test", default="14d")
    parser.add_argument("--steps", type=int, default=3)
    parser.add_argument("--promote-if", dest="promote_if", default="PF>=1.0")
    args = parser.parse_args()

    frame = load_data(args.csv)
    engine = BacktestEngine()
    profile_a = load_profile(args.profileA)
    profile_b = load_profile(args.profileB)

    result_a, result_b = run_ab_test(
        frame,
        (args.profileA.stem, profile_a),
        (args.profileB.stem, profile_b),
        engine=engine,
        train=args.train,
        test=args.test,
        steps=args.steps,
    )

    winner = decide_winner(result_a, result_b)
    promoted = False
    if winner.name == args.profileB.stem and parse_condition(args.promote_if, winner.metrics):
        shutil.copy(args.profileB, args.default)
        promoted = True

    payload = {
        "A": {"name": result_a.name, "metrics": result_a.metrics},
        "B": {"name": result_b.name, "metrics": result_b.metrics},
        "winner": winner.name,
        "promoted": promoted,
    }

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


if __name__ == "__main__":
    main()
