"""Autonomic risk monitor for live trading."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Callable, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class RiskState(str, Enum):
    NORMAL = "normal"
    CONSERVATIVE = "conservative"
    LOCK_IN = "lock_in"


@dataclass
class RiskSnapshot:
    timestamp: pd.Timestamp
    equity: float
    drawdown_pct: float
    profit_factor: float
    win_rate: float
    leverage_multiplier: float
    notes: str = ""


@dataclass
class RiskSettings:
    max_drawdown_pct: float = 10.0
    min_profit_factor: float = 1.3
    lock_in_profit_factor: float = 1.8
    recovery_trades: int = 20
    min_leverage: float = 0.5
    max_leverage: float = 1.5


class RiskMonitor:
    """Evaluate telemetry and emit leverage modifiers."""

    def __init__(
        self,
        *,
        settings: RiskSettings,
        on_state_change: Optional[Callable[[RiskState, RiskSnapshot], None]] = None,
    ) -> None:
        self.settings = settings
        self.on_state_change = on_state_change
        self.state: RiskState = RiskState.NORMAL
        self.history: List[RiskSnapshot] = []
        self.leverage_multiplier: float = 1.0

    def ingest_metrics(self, metrics: pd.DataFrame) -> RiskSnapshot:
        if metrics.empty:
            raise ValueError("metrics must not be empty")
        latest = metrics.iloc[-1]
        dd_pct = float(latest.get("drawdown_pct", 0.0))
        pf = float(latest.get("profit_factor", 0.0))
        win_rate = float(latest.get("win_rate", 0.0))
        equity = float(latest.get("equity", 0.0))
        timestamp = pd.to_datetime(latest.get("timestamp"))
        snapshot = RiskSnapshot(
            timestamp=timestamp,
            equity=equity,
            drawdown_pct=dd_pct,
            profit_factor=pf,
            win_rate=win_rate,
            leverage_multiplier=self.leverage_multiplier,
        )
        self.history.append(snapshot)
        self._evaluate_state(snapshot)
        return snapshot

    def _evaluate_state(self, snapshot: RiskSnapshot) -> None:
        previous_state = self.state
        if snapshot.drawdown_pct >= self.settings.max_drawdown_pct or snapshot.profit_factor <= self.settings.min_profit_factor:
            self.state = RiskState.CONSERVATIVE
            self.leverage_multiplier = max(self.settings.min_leverage, self.leverage_multiplier * 0.5)
            snapshot.notes = "drawdown or pf breach"
        elif snapshot.profit_factor >= self.settings.lock_in_profit_factor:
            self.state = RiskState.LOCK_IN
            self.leverage_multiplier = max(self.settings.min_leverage, self.leverage_multiplier * 0.75)
            snapshot.notes = "lock-in profits"
        else:
            self.state = RiskState.NORMAL
            self.leverage_multiplier = min(1.0, self.leverage_multiplier * 1.05)
            snapshot.notes = "normal"

        snapshot.leverage_multiplier = self.leverage_multiplier
        if previous_state != self.state:
            logger.info("risk state change %s -> %s", previous_state, self.state)
            if self.on_state_change:
                self.on_state_change(self.state, snapshot)

    def current_multiplier(self) -> float:
        return self.leverage_multiplier

    async def monitor_loop(self, metrics_provider: Callable[[], pd.DataFrame], interval: float = 60.0) -> None:
        while True:
            try:
                metrics = metrics_provider()
                if not metrics.empty:
                    self.ingest_metrics(metrics)
            except Exception as exc:  # pragma: no cover - safety net
                logger.exception("risk monitor failure: %s", exc)
            await asyncio.sleep(interval)
