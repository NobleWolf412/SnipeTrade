#!/usr/bin/env python3
"""Parameter optimisation CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from snipetrade.sim.engine import BacktestEngine
from snipetrade.sim.metrics import profit_factor
from snipetrade.tune.bayes import optimise as bayes_opt, parse_bounds
from snipetrade.tune.grid import build_grid, run_grid

from tools._snp_utils import load_data, load_profile, ThresholdProfile


def evaluate_profile(frame, profile: ThresholdProfile, train: str, test: str, steps: int) -> float:
    engine = BacktestEngine()
    result = engine.run_walk_forward(frame, profile, train=train, test=test, steps=steps)
    return result.combined_metrics.get("profit_factor", 0.0)


def grid_command(args: argparse.Namespace) -> Dict[str, Any]:
    frame = load_data(args.csv)
    base_profile = load_profile(args.profile)

    def evaluator(params: Dict[str, float]) -> float:
        merged = ThresholdProfile({**base_profile.params, **params})
        return evaluate_profile(frame, merged, args.train, args.test, args.steps)

    grid = build_grid(dict(param.split("=", 1) for param in args.params))
    results = run_grid(evaluator, grid, budget=args.budget, early_stop=args.early_stop)
    return {
        "best": results[0].params if results else {},
        "trials": [
            {"params": result.params, "score": result.score}
            for result in results
        ],
    }


def bayes_command(args: argparse.Namespace) -> Dict[str, Any]:
    frame = load_data(args.csv)
    base_profile = load_profile(args.profile)
    bounds = {key: parse_bounds(value) for key, value in (param.split("=", 1) for param in args.params)}

    def evaluator(params: Dict[str, float]) -> float:
        merged = ThresholdProfile({**base_profile.params, **params})
        return evaluate_profile(frame, merged, args.train, args.test, args.steps)

    result = bayes_opt(
        evaluator,
        bounds,
        trials=args.trials,
        warmup=args.warmup,
        top_k=args.top_k,
    )
    return {
        "best": result.best.params,
        "trials": [{"params": trial.params, "score": trial.score} for trial in result.trials],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Strategy optimisation")
    sub = parser.add_subparsers(dest="mode", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--profile", required=True, type=Path)
    common.add_argument("--csv", type=Path)
    common.add_argument("--train", default="30d")
    common.add_argument("--test", default="14d")
    common.add_argument("--steps", type=int, default=3)

    grid_parser = sub.add_parser("grid", parents=[common])
    grid_parser.add_argument("--params", nargs="+", required=True)
    grid_parser.add_argument("--budget", type=int, default=50)
    grid_parser.add_argument("--early-stop", type=int, default=0)
    grid_parser.add_argument("--report", required=True, type=Path)

    bayes_parser = sub.add_parser("bayes", parents=[common])
    bayes_parser.add_argument("--params", nargs="+", required=True)
    bayes_parser.add_argument("--trials", type=int, default=50)
    bayes_parser.add_argument("--warmup", type=int, default=10)
    bayes_parser.add_argument("--top-k", type=int, default=10)
    bayes_parser.add_argument("--report", required=True, type=Path)

    args = parser.parse_args()

    if args.mode == "grid":
        payload = grid_command(args)
    else:
        payload = bayes_command(args)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


if __name__ == "__main__":
    main()
