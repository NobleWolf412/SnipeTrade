"""Persistence helpers for live trading metrics."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


@dataclass
class MetricSample:
    timestamp: pd.Timestamp
    equity: float
    drawdown_pct: float
    profit_factor: float
    win_rate: float
    expectancy: float


class LiveMetricsStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS live_metrics (
                    timestamp TEXT PRIMARY KEY,
                    equity REAL,
                    drawdown_pct REAL,
                    profit_factor REAL,
                    win_rate REAL,
                    expectancy REAL
                )
                """
            )

    def record(self, samples: Iterable[MetricSample]) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO live_metrics
                    (timestamp, equity, drawdown_pct, profit_factor, win_rate, expectancy)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (
                        sample.timestamp.isoformat(),
                        sample.equity,
                        sample.drawdown_pct,
                        sample.profit_factor,
                        sample.win_rate,
                        sample.expectancy,
                    )
                    for sample in samples
                ],
            )

    def fetch_recent(self, limit: int = 500) -> pd.DataFrame:
        with sqlite3.connect(self.path) as conn:
            df = pd.read_sql_query(
                "SELECT * FROM live_metrics ORDER BY timestamp DESC LIMIT ?",
                conn,
                params=(limit,),
            )
        return df.sort_values("timestamp")
