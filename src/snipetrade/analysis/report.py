"""Weekly report generation."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

import pandas as pd

from snipetrade.state.journal import JournalEntry


@dataclass
class WeeklyReport:
    week: str
    entries: List[JournalEntry]

    def to_markdown(self) -> str:
        lines = [f"# Weekly Report {self.week}", ""]
        if not self.entries:
            lines.append("No trades logged.")
            return "\n".join(lines)
        total_pnl = sum(entry.pnl or 0.0 for entry in self.entries)
        lines.append(f"Total PnL: {total_pnl:.2f}")
        lines.append("")
        lines.append("| Symbol | Result | PnL | Reasons |")
        lines.append("| --- | --- | ---: | --- |")
        for entry in self.entries:
            reasons = ", ".join(entry.reasons)
            lines.append(
                f"| {entry.symbol} | {entry.outcome or '-'} | "
                f"{(entry.pnl or 0.0):.2f} | {reasons} |"
            )
        return "\n".join(lines)

    def to_csv(self, path: Path) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["symbol", "timestamp", "outcome", "pnl", "reasons"])
            for entry in self.entries:
                writer.writerow(
                    [
                        entry.symbol,
                        entry.timestamp.isoformat(),
                        entry.outcome or "",
                        entry.pnl or 0.0,
                        ";".join(entry.reasons),
                    ]
                )


def build_report(entries: Iterable[JournalEntry], week: str) -> WeeklyReport:
    return WeeklyReport(week=week, entries=list(entries))
