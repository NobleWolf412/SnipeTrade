"""Robustness analysis helpers."""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Sequence

import numpy as np

from .engine import TradeResult


@dataclass
class MonteCarloResult:
    distribution: Sequence[float]
    mean: float
    p05: float
    p95: float


def monte_carlo(trades: Sequence[TradeResult], runs: int = 500) -> MonteCarloResult:
    pnl = np.array([trade.pnl for trade in trades])
    if pnl.size == 0:
        return MonteCarloResult([], 0.0, 0.0, 0.0)

    totals = []
    rng = np.random.default_rng(42)
    for _ in range(runs):
        permuted = rng.permutation(pnl)
        totals.append(float(permuted.sum()))
    distribution = np.array(totals)
    return MonteCarloResult(
        distribution=distribution,
        mean=float(distribution.mean()),
        p05=float(np.quantile(distribution, 0.05)),
        p95=float(np.quantile(distribution, 0.95)),
    )


@dataclass
class ShockOutcome:
    shock: float
    profit_factor: float
    expectancy: float


def parameter_jitter(
    base_params: Dict[str, float],
    evaluator: Callable[[Dict[str, float]], float],
    *,
    percent: float = 0.1,
    samples: int = 32,
) -> Dict[str, float]:
    """Evaluate sensitivity by randomly perturbing parameters."""

    rng = np.random.default_rng(1337)
    results = {}
    for _ in range(samples):
        jittered = {
            key: value * (1 + rng.uniform(-percent, percent)) for key, value in base_params.items()
        }
        score = evaluator(jittered)
        results[tuple(sorted(jittered.items()))] = score
    return {"baseline": evaluator(base_params), "samples": results}


def slippage_shock(
    trades: Sequence[TradeResult],
    *,
    shocks: Iterable[float] = (-0.0005, -0.00025, 0.00025, 0.0005),
) -> List[ShockOutcome]:
    outcomes: List[ShockOutcome] = []
    base_pnl = np.array([trade.pnl for trade in trades])
    if base_pnl.size == 0:
        return outcomes

    for shock in shocks:
        adjusted = base_pnl * (1 + shock)
        wins = adjusted[adjusted > 0]
        losses = adjusted[adjusted <= 0]
        pf = wins.sum() / abs(losses.sum()) if losses.sum() != 0 else float("inf")
        exp = adjusted.mean()
        outcomes.append(ShockOutcome(shock=shock, profit_factor=float(pf), expectancy=float(exp)))
    return outcomes
