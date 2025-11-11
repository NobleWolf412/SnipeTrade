"""Simple metrics registry for autotrade execution."""

from __future__ import annotations

import asyncio
from collections import Counter, deque
from statistics import mean
from typing import Deque, Dict


class AutotradeMetrics:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._counters: Counter[str] = Counter()
        self._latencies: Deque[float] = deque(maxlen=100)

    async def incr(self, key: str, value: int = 1) -> None:
        async with self._lock:
            self._counters[key] += value

    async def observe_latency(self, key: str, value: float) -> None:
        async with self._lock:
            composite_key = f"latency_{key}"
            self._counters[composite_key] += 1
            self._latencies.append(value)

    async def snapshot(self) -> Dict[str, float]:
        async with self._lock:
            snapshot = dict(self._counters)
            if self._latencies:
                snapshot["latency_avg"] = mean(self._latencies)
                snapshot["latency_max"] = max(self._latencies)
            return snapshot


metrics = AutotradeMetrics()

__all__ = ["metrics", "AutotradeMetrics"]
