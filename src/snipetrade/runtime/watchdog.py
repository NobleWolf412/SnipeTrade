"""Watchdog monitors worker heartbeats and triggers guardian restarts."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Dict

logger = logging.getLogger(__name__)


@dataclass
class Heartbeat:
    name: str
    interval: float
    last_seen: float = field(default_factory=lambda: time.monotonic())


class Watchdog:
    def __init__(self, restart: Callable[[str], None]) -> None:
        self.restart = restart
        self.heartbeats: Dict[str, Heartbeat] = {}
        self.running = False

    def register(self, name: str, interval: float) -> None:
        self.heartbeats[name] = Heartbeat(name=name, interval=interval)

    def beat(self, name: str) -> None:
        if name in self.heartbeats:
            self.heartbeats[name].last_seen = time.monotonic()

    async def run(self, check_interval: float = 5.0) -> None:
        self.running = True
        while self.running:
            now = time.monotonic()
            for hb in list(self.heartbeats.values()):
                if now - hb.last_seen > hb.interval * 2:
                    logger.warning("worker %s stale, requesting restart", hb.name)
                    self.restart(hb.name)
                    hb.last_seen = now
            await asyncio.sleep(check_interval)

    def stop(self) -> None:
        self.running = False
