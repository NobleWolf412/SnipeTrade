"""Lightweight Bayesian optimiser using a TPE style surrogate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Sequence, Tuple

import numpy as np


@dataclass
class Trial:
    params: Dict[str, float]
    score: float


@dataclass
class BayesResult:
    trials: List[Trial]

    @property
    def best(self) -> Trial:
        return max(self.trials, key=lambda trial: trial.score)


def parse_bounds(spec: str) -> Tuple[float, float]:
    if not spec.startswith("[") or not spec.endswith("]"):
        raise ValueError("Bounds must be in the form [min,max]")
    lo, hi = spec[1:-1].split(",")
    return float(lo), float(hi)


def _sample_param(bounds: Tuple[float, float], rng: np.random.Generator) -> float:
    lo, hi = bounds
    return float(rng.uniform(lo, hi))


def _sample_from_best(
    key: str,
    best_trials: List[Trial],
    bounds: Tuple[float, float],
    rng: np.random.Generator,
) -> float:
    values = [trial.params[key] for trial in best_trials]
    mean = float(np.mean(values))
    std = float(np.std(values) or (bounds[1] - bounds[0]) / 6)
    sample = float(rng.normal(mean, std))
    return float(np.clip(sample, bounds[0], bounds[1]))


def optimise(
    evaluator: Callable[[Dict[str, float]], float],
    bounds: Dict[str, Tuple[float, float]],
    *,
    trials: int,
    warmup: int = 5,
    top_k: int = 10,
    seed: int | None = None,
) -> BayesResult:
    rng = np.random.default_rng(seed)
    history: List[Trial] = []

    for i in range(trials):
        if i < warmup or len(history) < top_k:
            params = {key: _sample_param(bound, rng) for key, bound in bounds.items()}
        else:
            best_trials = sorted(history, key=lambda trial: trial.score, reverse=True)[:top_k]
            params = {
                key: _sample_from_best(key, best_trials, bounds[key], rng) for key in bounds.keys()
            }
        score = evaluator(params)
        history.append(Trial(params=params, score=score))

    return BayesResult(history)
