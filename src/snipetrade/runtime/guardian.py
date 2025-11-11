"""Process guardian that supervises bot workers."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable, Dict

logger = logging.getLogger(__name__)


@dataclass
class WorkerSpec:
    name: str
    start: Callable[[], Awaitable[None]]


class Guardian:
    def __init__(self) -> None:
        self.workers: Dict[str, WorkerSpec] = {}
        self.tasks: Dict[str, asyncio.Task[None]] = {}

    def register(self, spec: WorkerSpec) -> None:
        self.workers[spec.name] = spec

    async def ensure_running(self, name: str) -> None:
        if name in self.tasks and not self.tasks[name].done():
            return
        spec = self.workers[name]
        logger.info("starting worker %s", name)
        task = asyncio.create_task(self._run_worker(spec))
        self.tasks[name] = task

    async def _run_worker(self, spec: WorkerSpec) -> None:
        while True:
            try:
                await spec.start()
            except Exception as exc:  # pragma: no cover - resilience
                logger.exception("worker %s crashed: %s", spec.name, exc)
                await asyncio.sleep(1)
            else:
                logger.info("worker %s completed normally", spec.name)
                break

    async def run(self) -> None:
        await asyncio.gather(*(self.ensure_running(name) for name in self.workers))
        await asyncio.gather(*self.tasks.values())
