"""Adaptive calibration from live trading journal."""

from __future__ import annotations

import datetime as _dt
import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import pandas as pd


@dataclass
class TradeRecord:
    """Normalized representation of a closed trade."""

    opened_at: _dt.datetime
    closed_at: _dt.datetime
    symbol: str
    side: str
    pnl: float
    risk: float
    rr: float
    atr: float
    outcome: str
    meta: Dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_row(cls, row: Dict[str, object]) -> "TradeRecord":
        opened = pd.to_datetime(row.get("opened_at"))
        closed = pd.to_datetime(row.get("closed_at"))
        return cls(
            opened_at=opened.to_pydatetime() if not pd.isna(opened) else _dt.datetime.min,
            closed_at=closed.to_pydatetime() if not pd.isna(closed) else _dt.datetime.min,
            symbol=str(row.get("symbol", "")),
            side=str(row.get("side", "")),
            pnl=float(row.get("pnl", 0.0)),
            risk=float(row.get("risk", 0.0)),
            rr=float(row.get("rr", 0.0)),
            atr=float(row.get("atr", 0.0)),
            outcome=str(row.get("outcome", "flat")),
            meta={k: float(v) for k, v in row.items() if isinstance(v, (int, float)) and k not in {"pnl", "risk", "rr", "atr"}},
        )


@dataclass
class CalibrationProposal:
    generated_at: _dt.datetime
    lookback_start: _dt.datetime
    lookback_end: _dt.datetime
    baseline_metrics: Dict[str, float]
    suggested_metrics: Dict[str, float]
    adjustments: Dict[str, float]
    trade_count: int
    notes: str = ""

    @property
    def proposal_id(self) -> str:
        return self.generated_at.strftime("%Y%m%dT%H%M%S")

    def to_json(self) -> Dict[str, object]:
        return {
            "proposal_id": self.proposal_id,
            "generated_at": self.generated_at.isoformat(),
            "lookback_start": self.lookback_start.isoformat(),
            "lookback_end": self.lookback_end.isoformat(),
            "baseline_metrics": self.baseline_metrics,
            "suggested_metrics": self.suggested_metrics,
            "adjustments": self.adjustments,
            "trade_count": self.trade_count,
            "notes": self.notes,
        }


class AdaptiveCalibrator:
    """Compute calibration deltas from live trades.

    The calibrator consumes a trade journal (CSV or DuckDB query) and
    evaluates a set of guard-rail metrics.  It emits a proposal that can be
    inspected in the dashboard and optionally promoted to an active profile.
    """

    def __init__(
        self,
        journal_path: Path,
        *,
        max_rr_adjustment: float = 5.0,
        max_atr_adjustment: float = 0.25,
        max_quality_adjustment: float = 0.2,
    ) -> None:
        self.journal_path = Path(journal_path)
        self.max_rr_adjustment = max_rr_adjustment
        self.max_atr_adjustment = max_atr_adjustment
        self.max_quality_adjustment = max_quality_adjustment

    def _load_trades(self, lookback_days: int) -> List[TradeRecord]:
        if not self.journal_path.exists():
            return []
        if self.journal_path.suffix.lower() == ".csv":
            df = pd.read_csv(self.journal_path)
        elif self.journal_path.suffix.lower() in {".parquet", ".pq"}:
            df = pd.read_parquet(self.journal_path)
        else:
            raise ValueError(f"Unsupported journal format: {self.journal_path.suffix}")

        df["closed_at"] = pd.to_datetime(df.get("closed_at"))
        if "closed_at" not in df.columns:
            raise ValueError("journal requires closed_at column")
        lookback_threshold = pd.Timestamp.utcnow() - pd.Timedelta(days=lookback_days)
        df = df[df["closed_at"] >= lookback_threshold]
        return [TradeRecord.from_row(row._asdict()) for row in df.itertuples(index=False)]

    @staticmethod
    def _baseline_metrics(trades: Sequence[TradeRecord]) -> Dict[str, float]:
        pnl = [t.pnl for t in trades]
        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl < 0]
        risk = [abs(t.risk) for t in trades if t.risk]
        rr = [t.rr for t in trades if t.rr]
        atr = [t.atr for t in trades if t.atr]
        win_rate = len(wins) / len(trades) if trades else 0.0
        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        profit_factor = gross_profit / gross_loss if gross_loss else float("inf") if gross_profit else 0.0
        expectancy = statistics.mean(pnl) if pnl else 0.0
        avg_rr = statistics.mean(rr) if rr else 0.0
        avg_atr = statistics.mean(atr) if atr else 0.0
        median_risk = statistics.median(risk) if risk else 0.0
        return {
            "trade_count": float(len(trades)),
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "expectancy": expectancy,
            "avg_rr": avg_rr,
            "avg_atr": avg_atr,
            "median_risk": median_risk,
            "max_drawdown": AdaptiveCalibrator._max_drawdown(pnl),
        }

    @staticmethod
    def _max_drawdown(pnl: Sequence[float]) -> float:
        equity = 0.0
        peak = 0.0
        max_dd = 0.0
        for change in pnl:
            equity += change
            peak = max(peak, equity)
            drawdown = peak - equity
            max_dd = max(max_dd, drawdown)
        return max_dd

    def _suggest_adjustments(self, metrics: Dict[str, float]) -> Dict[str, float]:
        adjustments: Dict[str, float] = {}
        if metrics["win_rate"] < 0.45 and metrics["avg_rr"] < 2:
            adjustments["rr_min"] = min(self.max_rr_adjustment, 2.0 - metrics["avg_rr"])
        if metrics["profit_factor"] < 1.1:
            adjustments["atr_guard"] = min(self.max_atr_adjustment, 0.1)
        if metrics["max_drawdown"] > 0:
            quality_penalty = min(metrics["max_drawdown"] / max(metrics["median_risk"], 1e-6), self.max_quality_adjustment)
            adjustments["ob_quality"] = -quality_penalty
        return adjustments

    def _apply_adjustments(self, adjustments: Dict[str, float]) -> Dict[str, float]:
        # Provide suggested metrics derived from adjustments. The caller can
        # merge these into strategy configs.
        suggested = {}
        if "rr_min" in adjustments:
            suggested["rr_min"] = adjustments["rr_min"]
        if "atr_guard" in adjustments:
            suggested["atr_guard"] = adjustments["atr_guard"]
        if "ob_quality" in adjustments:
            suggested["ob_quality_delta"] = adjustments["ob_quality"]
        return suggested

    def generate_proposal(
        self,
        *,
        lookback_days: int = 7,
        save_to: Optional[Path] = None,
    ) -> CalibrationProposal:
        trades = self._load_trades(lookback_days)
        metrics = self._baseline_metrics(trades)
        adjustments = self._suggest_adjustments(metrics)
        suggested = self._apply_adjustments(adjustments)
        proposal = CalibrationProposal(
            generated_at=_dt.datetime.utcnow(),
            lookback_start=_dt.datetime.utcnow() - _dt.timedelta(days=lookback_days),
            lookback_end=_dt.datetime.utcnow(),
            baseline_metrics=metrics,
            suggested_metrics=suggested,
            adjustments=adjustments,
            trade_count=len(trades),
            notes="auto-generated",
        )
        if save_to:
            save_to = Path(save_to)
            if save_to.is_dir():
                save_to = save_to / f"{proposal.proposal_id}.json"
            save_to.parent.mkdir(parents=True, exist_ok=True)
            with save_to.open("w", encoding="utf-8") as f:
                json.dump(proposal.to_json(), f, indent=2)
        return proposal


def summarize_proposals(path: Path) -> List[CalibrationProposal]:
    proposals: List[CalibrationProposal] = []
    for file in sorted(Path(path).glob("*.json")):
        with file.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        proposals.append(
            CalibrationProposal(
                generated_at=_dt.datetime.fromisoformat(payload["generated_at"]),
                lookback_start=_dt.datetime.fromisoformat(payload["lookback_start"]),
                lookback_end=_dt.datetime.fromisoformat(payload["lookback_end"]),
                baseline_metrics=payload["baseline_metrics"],
                suggested_metrics=payload["suggested_metrics"],
                adjustments=payload["adjustments"],
                trade_count=int(payload["trade_count"]),
                notes=payload.get("notes", ""),
            )
        )
    return proposals
