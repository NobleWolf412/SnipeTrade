"""Backtesting engine with walk-forward support."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Iterator, List, Optional, Protocol, Sequence, Tuple

import numpy as np
import pandas as pd

from .datasets import DatasetWindow, walk_forward_windows


@dataclass
class TradeSpec:
    """Definition of an intended trade produced by a strategy."""

    symbol: str
    direction: str  # "long" or "short"
    entry: float
    stop: float
    targets: Sequence[float]
    timestamp: pd.Timestamp
    size: float = 1.0
    target_allocations: Optional[Sequence[float]] = None
    timeout: Optional[pd.Timestamp] = None
    maker: bool = False
    stop_order: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    breakeven_after_tp1: bool = True


@dataclass
class TradeResult:
    """Executed trade details returned by the engine."""

    spec: TradeSpec
    filled: bool
    entry_time: Optional[pd.Timestamp]
    exit_time: Optional[pd.Timestamp]
    avg_entry: float
    avg_exit: float
    pnl: float
    fee: float
    funding: float
    partial: float
    path: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def gross(self) -> float:
        return self.pnl + self.fee + self.funding


class StrategyProfile(Protocol):
    """Minimal protocol required by the engine."""

    def prepare(self, train: pd.DataFrame) -> Any:
        ...

    def generate(self, test: pd.DataFrame, context: Any) -> Iterable[TradeSpec]:
        ...


@dataclass
class WalkForwardIteration:
    train_window: DatasetWindow
    test_window: DatasetWindow
    trades: List[TradeResult]
    metrics: Dict[str, float]


@dataclass
class WalkForwardResult:
    iterations: List[WalkForwardIteration]
    combined_metrics: Dict[str, float]


class BacktestEngine:
    """Simulate trades produced by a :class:`StrategyProfile`."""

    def __init__(
        self,
        *,
        slippage_bps: float = 2.5,
        taker_fee_bps: float = 7.5,
        maker_fee_bps: float = -2.0,
        funding_rate_per_hour: float = 0.0,
        seed: Optional[int] = None,
    ) -> None:
        self.slippage_bps = slippage_bps
        self.taker_fee_bps = taker_fee_bps
        self.maker_fee_bps = maker_fee_bps
        self.funding_rate_per_hour = funding_rate_per_hour
        self.random_state = np.random.default_rng(seed)

    def run_walk_forward(
        self,
        frame: pd.DataFrame,
        profile: StrategyProfile,
        *,
        train: str,
        test: str,
        steps: int,
    ) -> WalkForwardResult:
        """Execute a walk-forward simulation using the provided profile."""

        iterations: List[WalkForwardIteration] = []
        combined_trades: List[TradeResult] = []

        for train_window, test_window in walk_forward_windows(
            frame, train=train, test=test, steps=steps
        ):
            context = profile.prepare(train_window.frame)
            trades = list(self._simulate_window(test_window.frame, profile, context))
            metrics = self._summarise(trades)
            iterations.append(
                WalkForwardIteration(
                    train_window=train_window,
                    test_window=test_window,
                    trades=trades,
                    metrics=metrics,
                )
            )
            combined_trades.extend(trades)

        combined_metrics = self._summarise(combined_trades)
        return WalkForwardResult(iterations=iterations, combined_metrics=combined_metrics)

    def _simulate_window(
        self, test_frame: pd.DataFrame, profile: StrategyProfile, context: Any
    ) -> Iterator[TradeResult]:
        for spec in profile.generate(test_frame, context):
            yield self._simulate_trade(spec, test_frame)

    def _simulate_trade(self, spec: TradeSpec, frame: pd.DataFrame) -> TradeResult:
        candles = frame.loc[frame.index >= spec.timestamp]
        if candles.empty:
            return TradeResult(
                spec=spec,
                filled=False,
                entry_time=None,
                exit_time=None,
                avg_entry=spec.entry,
                avg_exit=spec.entry,
                pnl=0.0,
                fee=0.0,
                funding=0.0,
                partial=0.0,
            )

        allocations = (
            list(spec.target_allocations)
            if spec.target_allocations is not None
            else [1.0 / max(len(spec.targets), 1)] * len(spec.targets)
        )
        allocations = [max(a, 0.0) for a in allocations]
        total_alloc = sum(allocations)
        allocations = [a / total_alloc for a in allocations] if total_alloc else allocations

        remaining_size = spec.size
        entry_price = spec.entry
        entry_time: Optional[pd.Timestamp] = None
        exit_price = entry_price
        exit_time: Optional[pd.Timestamp] = None
        fee_acc = 0.0
        funding_acc = 0.0
        pnl_acc = 0.0
        filled = False
        price_col = "close"
        path: List[Dict[str, Any]] = []

        stop = spec.stop
        breakeven_enabled = spec.breakeven_after_tp1 and len(spec.targets) > 0
        last_funding_timestamp: Optional[pd.Timestamp] = None

        for ts, candle in candles.iterrows():
            if spec.timeout and ts > spec.timeout:
                break

            high = candle["high"]
            low = candle["low"]
            open_ = candle["open"]
            close = candle[price_col]

            if not filled:
                trigger = False
                if spec.direction == "long":
                    if spec.maker:
                        trigger = low <= entry_price <= high
                    elif spec.stop_order:
                        trigger = high >= entry_price
                    else:
                        trigger = low <= entry_price
                else:
                    if spec.maker:
                        trigger = low <= entry_price <= high
                    elif spec.stop_order:
                        trigger = low <= entry_price
                    else:
                        trigger = high >= entry_price

                if trigger:
                    filled = True
                    entry_time = ts
                    slippage = self._slippage(entry_price, spec.direction, spec.maker)
                    entry_price += slippage
                    fee_acc += self._fee(entry_price, spec.size, spec.maker)
                    path.append(
                        {
                            "event": "entry",
                            "timestamp": ts,
                            "price": entry_price,
                            "slippage": slippage,
                        }
                    )
                    last_funding_timestamp = ts
                    continue

            if not filled:
                continue

            # Funding accrues per candle proportional to holding period length (minutes).
            if last_funding_timestamp is not None and ts > last_funding_timestamp:
                funding_acc += self._funding(
                    entry_price,
                    remaining_size,
                    last_funding_timestamp,
                    ts,
                )
                last_funding_timestamp = ts

            outcome = self._evaluate_targets(
                spec,
                allocations,
                remaining_size,
                stop,
                entry_price,
                high,
                low,
                ts,
            )

            remaining_size = outcome.remaining_size
            pnl_acc += outcome.realised_pnl
            fee_acc += outcome.fee
            exit_record = outcome.exit_record
            stop = outcome.stop
            if breakeven_enabled and outcome.tp_index == 0:
                stop = entry_price

            if exit_record is not None:
                exit_time = ts
                exit_price = exit_record["price"]
                path.append(exit_record)

            path.extend(outcome.partial_records)

            if remaining_size <= 1e-9:
                remaining_size = 0.0
                last_funding_timestamp = None
                break

        if filled and remaining_size > 0:
            # Force exit at final candle close
            last_close = candles.iloc[-1][price_col]
            direction_factor = 1 if spec.direction == "long" else -1
            pnl_acc += direction_factor * (last_close - entry_price) * remaining_size
            fee_acc += self._fee(last_close, remaining_size, False)
            exit_price = last_close
            exit_time = candles.index[-1]
            path.append(
                {
                    "event": "force_exit",
                    "timestamp": exit_time,
                    "price": exit_price,
                    "size": remaining_size,
                }
            )
            remaining_size = 0.0
            last_funding_timestamp = None

        return TradeResult(
            spec=spec,
            filled=filled,
            entry_time=entry_time,
            exit_time=exit_time,
            avg_entry=entry_price,
            avg_exit=exit_price,
            pnl=pnl_acc,
            fee=fee_acc,
            funding=funding_acc,
            partial=spec.size - remaining_size if filled else 0.0,
            path=path,
        )

    def _evaluate_targets(
        self,
        spec: TradeSpec,
        allocations: Sequence[float],
        remaining_size: float,
        stop: float,
        entry_price: float,
        high: float,
        low: float,
        timestamp: pd.Timestamp,
    ) -> "_TargetOutcome":
        direction_factor = 1 if spec.direction == "long" else -1
        realised = 0.0
        fee = 0.0
        exit_record: Optional[Dict[str, Any]] = None
        partial_records: List[Dict[str, Any]] = []
        new_stop = stop
        tp_index = -1

        for idx, (target, allocation) in enumerate(zip(spec.targets, allocations)):
            target_hit = False
            if spec.direction == "long":
                if high >= target:
                    target_hit = True
            else:
                if low <= target:
                    target_hit = True

            if not target_hit:
                continue

            size = remaining_size * allocation
            remaining_size -= size
            exit_price = target - self._slippage(target, spec.direction, False)
            realised += direction_factor * (exit_price - entry_price) * size
            fee += self._fee(exit_price, size, False)
            partial_records.append(
                {
                    "event": "target",
                    "target_index": idx,
                    "timestamp": timestamp,
                    "price": exit_price,
                    "size": size,
                }
            )
            tp_index = idx
            if remaining_size <= 1e-9:
                exit_record = {
                    "event": "final_exit",
                    "timestamp": timestamp,
                    "price": exit_price,
                    "size": size,
                }
                break

            if spec.breakeven_after_tp1 and idx == 0:
                new_stop = entry_price

        stop_hit = False
        if remaining_size > 0:
            if spec.direction == "long":
                stop_hit = low <= new_stop
            else:
                stop_hit = high >= new_stop

        if stop_hit:
            exit_price = new_stop + self._slippage(new_stop, spec.direction, False)
            realised += direction_factor * (exit_price - entry_price) * remaining_size
            fee += self._fee(exit_price, remaining_size, False)
            exit_record = {
                "event": "stop",
                "timestamp": timestamp,
                "price": exit_price,
                "size": remaining_size,
            }
            remaining_size = 0.0

        return _TargetOutcome(
            remaining_size=remaining_size,
            realised_pnl=realised,
            fee=fee,
            exit_record=exit_record,
            partial_records=partial_records,
            stop=new_stop,
            tp_index=tp_index,
        )

    def _slippage(self, price: float, direction: str, maker: bool) -> float:
        bps = self.maker_fee_bps if maker else self.slippage_bps
        factor = 1 if direction == "long" else -1
        return factor * price * bps / 10_000.0

    def _fee(self, price: float, size: float, maker: bool) -> float:
        bps = self.maker_fee_bps if maker else self.taker_fee_bps
        direction = 1 if maker else 1
        return -direction * price * size * bps / 10_000.0

    def _funding(
        self,
        entry_price: float,
        size: float,
        start: Optional[pd.Timestamp],
        end: pd.Timestamp,
    ) -> float:
        if start is None or self.funding_rate_per_hour == 0.0:
            return 0.0
        delta_minutes = (end - start).total_seconds() / 60.0
        if delta_minutes <= 0:
            return 0.0
        return -entry_price * size * self.funding_rate_per_hour * (delta_minutes / 60.0)

    def _summarise(self, trades: Sequence[TradeResult]) -> Dict[str, float]:
        pnl = [trade.pnl for trade in trades if trade.filled]
        wins = [p for p in pnl if p > 0]
        losses = [p for p in pnl if p <= 0]
        profit_factor = sum(wins) / abs(sum(losses)) if losses else float("inf")
        expectancy = statistics.mean(pnl) if pnl else 0.0
        max_loss = min(pnl) if pnl else 0.0
        equity = []
        total = 0.0
        for trade in trades:
            if not trade.filled:
                continue
            total += trade.pnl
            equity.append(total)
        max_dd = 0.0
        peak = -float("inf")
        for value in equity:
            if value > peak:
                peak = value
            drawdown = peak - value
            if drawdown > max_dd:
                max_dd = drawdown
        return {
            "total_trades": float(len(trades)),
            "filled_trades": float(sum(1 for trade in trades if trade.filled)),
            "profit_factor": profit_factor,
            "expectancy": expectancy,
            "max_loss": max_loss,
            "max_drawdown": max_dd,
        }


@dataclass
class _TargetOutcome:
    remaining_size: float
    realised_pnl: float
    fee: float
    exit_record: Optional[Dict[str, Any]]
    partial_records: List[Dict[str, Any]]
    stop: float
    tp_index: int
