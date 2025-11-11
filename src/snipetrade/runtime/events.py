"""Event driven rule engine for runtime automations."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List

import yaml

logger = logging.getLogger(__name__)


@dataclass
class EventRule:
    name: str
    condition: Dict[str, float]
    action: Dict[str, str]


class EventEngine:
    """Evaluate metrics against declarative rules."""

    def __init__(self, rules: Iterable[EventRule], dispatcher: Callable[[Dict[str, str]], None]) -> None:
        self.rules = list(rules)
        self.dispatcher = dispatcher

    @classmethod
    def from_yaml(cls, path: Path, dispatcher: Callable[[Dict[str, str]], None]) -> "EventEngine":
        payload = yaml.safe_load(Path(path).read_text()) or {}
        rules = [EventRule(name=rule["name"], condition=rule["when"], action=rule["then"]) for rule in payload.get("rules", [])]
        return cls(rules, dispatcher)

    def evaluate(self, metrics: Dict[str, float]) -> List[str]:
        triggered: List[str] = []
        for rule in self.rules:
            if self._match(rule.condition, metrics):
                logger.info("event triggered: %s", rule.name)
                self.dispatcher(rule.action)
                triggered.append(rule.name)
        return triggered

    @staticmethod
    def _match(condition: Dict[str, float], metrics: Dict[str, float]) -> bool:
        for key, value in condition.items():
            if key.endswith("_lt"):
                field = key[:-3]
                if metrics.get(field, float("inf")) >= value:
                    return False
            elif key.endswith("_gt"):
                field = key[:-3]
                if metrics.get(field, float("-inf")) <= value:
                    return False
            else:
                if metrics.get(key) != value:
                    return False
        return True
