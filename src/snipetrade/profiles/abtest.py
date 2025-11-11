"""Profile A/B testing helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Tuple

import pandas as pd

from snipetrade.sim.engine import BacktestEngine, StrategyProfile
from snipetrade.sim.metrics import equity_curve, expectancy, profit_factor


@dataclass
class ProfileResult:
    name: str
    metrics: Dict[str, float]


def run_ab_test(
    frame: pd.DataFrame,
    profile_a: Tuple[str, StrategyProfile],
    profile_b: Tuple[str, StrategyProfile],
    *,
    engine: BacktestEngine,
    train: str,
    test: str,
    steps: int,
) -> Tuple[ProfileResult, ProfileResult]:
    """Run walk-forward backtests for two profiles and compare metrics."""

    name_a, strat_a = profile_a
    name_b, strat_b = profile_b

    result_a = engine.run_walk_forward(frame, strat_a, train=train, test=test, steps=steps)
    result_b = engine.run_walk_forward(frame, strat_b, train=train, test=test, steps=steps)

    metrics_a = {
        "profit_factor": result_a.combined_metrics.get("profit_factor", 0.0),
        "expectancy": result_a.combined_metrics.get("expectancy", 0.0),
        "max_loss": result_a.combined_metrics.get("max_loss", 0.0),
    }
    metrics_b = {
        "profit_factor": result_b.combined_metrics.get("profit_factor", 0.0),
        "expectancy": result_b.combined_metrics.get("expectancy", 0.0),
        "max_loss": result_b.combined_metrics.get("max_loss", 0.0),
    }

    return ProfileResult(name_a, metrics_a), ProfileResult(name_b, metrics_b)
