"""Backtest metrics helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np

from .engine import TradeResult


@dataclass
class ExpectancyBreakdown:
    expectancy: float
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float


def profit_factor(trades: Sequence[TradeResult]) -> float:
    wins = [trade.pnl for trade in trades if trade.pnl > 0]
    losses = [trade.pnl for trade in trades if trade.pnl <= 0]
    if not wins:
        return 0.0
    if not losses:
        return float("inf")
    return sum(wins) / abs(sum(losses))


def expectancy(trades: Sequence[TradeResult]) -> ExpectancyBreakdown:
    pnl = [trade.pnl for trade in trades]
    if not pnl:
        return ExpectancyBreakdown(0.0, 0.0, 0.0, 0.0, 0.0)

    wins = [p for p in pnl if p > 0]
    losses = [p for p in pnl if p <= 0]
    total = len(pnl)
    avg_win = float(np.mean(wins)) if wins else 0.0
    avg_loss = float(np.mean(losses)) if losses else 0.0
    exp = float(np.mean(pnl))
    pf = profit_factor(trades)
    win_rate = len(wins) / total if total else 0.0
    return ExpectancyBreakdown(exp, win_rate, avg_win, avg_loss, pf)


def max_drawdown(equity: Iterable[float]) -> float:
    drawdown = 0.0
    peak = -float("inf")
    for value in equity:
        if value > peak:
            peak = value
        drawdown = min(drawdown, value - peak)
    return abs(drawdown)


def mar_ratio(equity: Sequence[float], years: float = 1.0) -> float:
    if not equity:
        return 0.0
    start = equity[0]
    end = equity[-1]
    if start <= 0:
        return 0.0
    cagr = (end / start) ** (1.0 / max(years, 1e-9)) - 1.0
    mdd = max_drawdown(equity)
    if mdd == 0:
        return float("inf")
    return cagr / mdd


def equity_curve(trades: Sequence[TradeResult]) -> Sequence[float]:
    total = 0.0
    curve = []
    for trade in trades:
        total += trade.pnl
        curve.append(total)
    return curve


def outlier_analysis(trades: Sequence[TradeResult], threshold: float = 0.95) -> dict:
    if not trades:
        return {"threshold": threshold, "cutoff": 0.0, "outliers": []}
    pnl = np.array([trade.pnl for trade in trades])
    cutoff = float(np.quantile(np.abs(pnl), threshold))
    mask = np.abs(pnl) >= cutoff
    outliers = [trades[i] for i, flag in enumerate(mask) if flag]
    return {"threshold": threshold, "cutoff": cutoff, "outliers": outliers}
