"""Trade journaling helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd


@dataclass
class JournalEntry:
    symbol: str
    timestamp: pd.Timestamp
    status: str
    reasons: List[str]
    score: float
    filled: bool = False
    outcome: Optional[str] = None
    pnl: Optional[float] = None
    extra: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        payload = asdict(self)
        payload["timestamp"] = self.timestamp.isoformat()
        return payload


class TradeJournal:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.entries: List[JournalEntry] = []
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, entry: JournalEntry) -> None:
        self.entries.append(entry)

    def flush(self) -> None:
        serialised = [entry.to_dict() for entry in self.entries]
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(serialised, handle, indent=2)

    def reason_heatmap(self) -> Dict[str, Dict[str, float]]:
        stats: Dict[str, Dict[str, float]] = {}
        for entry in self.entries:
            for reason in entry.reasons:
                bucket = stats.setdefault(reason, {"count": 0, "wins": 0})
                bucket["count"] += 1
                if entry.pnl and entry.pnl > 0:
                    bucket["wins"] += 1
        for bucket in stats.values():
            count = bucket["count"]
            bucket["win_rate"] = bucket["wins"] / count if count else 0.0
        return stats

    def per_symbol(self) -> Dict[str, Dict[str, float]]:
        stats: Dict[str, Dict[str, float]] = {}
        for entry in self.entries:
            bucket = stats.setdefault(entry.symbol, {"count": 0, "pnl": 0.0})
            bucket["count"] += 1
            if entry.pnl:
                bucket["pnl"] += entry.pnl
        return stats
