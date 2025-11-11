"""Grid search utilities for strategy parameters."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Callable, Dict, Iterable, Iterator, List, Sequence, Tuple


@dataclass
class GridResult:
    params: Dict[str, float]
    score: float


class ParameterGrid:
    def __init__(self, values: Dict[str, Sequence[float]]):
        self.values = values

    def __iter__(self) -> Iterator[Dict[str, float]]:
        keys = sorted(self.values.keys())
        for combo in product(*(self.values[key] for key in keys)):
            yield {key: value for key, value in zip(keys, combo)}

    def __len__(self) -> int:
        length = 1
        for values in self.values.values():
            length *= len(values)
        return length


def parse_range(spec: str) -> Sequence[float]:
    start, rest = spec.split("..")
    end, steps_part = rest.split("x")
    steps = int(steps_part)
    start_f = float(start)
    end_f = float(end)
    if steps == 1:
        return [start_f]
    step = (end_f - start_f) / (steps - 1)
    return [start_f + i * step for i in range(steps)]


def build_grid(param_specs: Dict[str, str]) -> ParameterGrid:
    values = {key: parse_range(value) for key, value in param_specs.items()}
    return ParameterGrid(values)


def run_grid(
    evaluator: Callable[[Dict[str, float]], float],
    grid: ParameterGrid,
    *,
    budget: int,
    early_stop: int = 0,
) -> List[GridResult]:
    """Evaluate grid search returning the top scoring configurations."""

    results: List[GridResult] = []
    best_score = float("-inf")
    stagnation = 0
    for i, params in enumerate(grid):
        if i >= budget:
            break
        score = evaluator(params)
        results.append(GridResult(params=params, score=score))
        if score > best_score:
            best_score = score
            stagnation = 0
        else:
            stagnation += 1
        if early_stop and stagnation >= early_stop:
            break
    results.sort(key=lambda item: item.score, reverse=True)
    return results
