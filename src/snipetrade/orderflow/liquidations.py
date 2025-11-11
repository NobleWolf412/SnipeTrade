"""Helpers for liquidation maps."""

from __future__ import annotations

from typing import Iterable, List, Tuple


def liq_density(bins: Iterable[Tuple[float, float]]) -> float:
    """Return liquidation size density per price unit."""

    prices: List[float] = []
    total = 0.0
    for price, size in bins:
        try:
            prices.append(float(price))
            total += max(float(size), 0.0)
        except (TypeError, ValueError):
            continue
    if not prices:
        return 0.0
    span = max(prices) - min(prices)
    if span <= 0:
        return total
    return total / span


def nearest_liq_cluster(price: float, clusters: Iterable[float]) -> float:
    """Return distance to the nearest liquidation cluster."""

    try:
        target = float(price)
    except (TypeError, ValueError):
        return float("inf")

    best = float("inf")
    for cluster in clusters:
        try:
            dist = abs(float(cluster) - target)
        except (TypeError, ValueError):
            continue
        if dist < best:
            best = dist
    return best
