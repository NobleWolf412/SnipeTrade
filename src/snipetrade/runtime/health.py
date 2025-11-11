"""Health tracking for the autotrader runtime."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from statistics import mean
from typing import Deque, Dict


@dataclass
class HealthSnapshot:
    status: str
    latency_ms: float
    error_rate: float
    total_requests: int
    details: Dict[str, float]


class AutotradeHealth:
    def __init__(self, sample_size: int = 120) -> None:
        self._latencies: Deque[float] = deque(maxlen=sample_size)
        self._success = 0
        self._errors = 0

    def record_success(self, latency_ms: float) -> None:
        self._latencies.append(latency_ms)
        self._success += 1

    def record_failure(self, latency_ms: float) -> None:
        self._latencies.append(latency_ms)
        self._errors += 1

    def snapshot(self) -> HealthSnapshot:
        total = self._success + self._errors
        error_rate = (self._errors / total) if total else 0.0
        avg_latency = mean(self._latencies) if self._latencies else 0.0
        status = "green"
        if error_rate > 0.1 or avg_latency > 1_000:
            status = "red"
        elif error_rate > 0.05 or avg_latency > 500:
            status = "yellow"
        return HealthSnapshot(
            status=status,
            latency_ms=avg_latency,
            error_rate=error_rate,
            total_requests=total,
            details={"max_latency_ms": max(self._latencies, default=0.0)},
        )


health = AutotradeHealth()

__all__ = ["AutotradeHealth", "HealthSnapshot", "health"]
