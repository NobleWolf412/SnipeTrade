"""Calibration proposal promotion workflow."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from .calibration import CalibrationProposal, summarize_proposals


@dataclass
class PromotionRecord:
    proposal_path: Path
    approved_at: str
    approved_by: str
    notes: str

    def to_json(self) -> Dict[str, str]:
        return {
            "proposal": str(self.proposal_path),
            "approved_at": self.approved_at,
            "approved_by": self.approved_by,
            "notes": self.notes,
        }


class CalibrationPromoter:
    """Persisted promotion workflow for calibration proposals."""

    def __init__(self, proposals_dir: Path, approvals_dir: Path) -> None:
        self.proposals_dir = Path(proposals_dir)
        self.approvals_dir = Path(approvals_dir)
        self.approvals_dir.mkdir(parents=True, exist_ok=True)

    def pending(self) -> List[CalibrationProposal]:
        approved = {p.stem for p in self.approvals_dir.glob("*.json")}
        return [p for p in summarize_proposals(self.proposals_dir) if p.proposal_id not in approved]

    def approve(self, proposal: CalibrationProposal, *, approver: str, notes: str = "") -> Path:
        filename = f"{proposal.proposal_id}.json"
        approval_path = self.approvals_dir / filename
        record = PromotionRecord(
            proposal_path=self._proposal_path(filename),
            approved_at=proposal.generated_at.isoformat(),
            approved_by=approver,
            notes=notes,
        )
        with approval_path.open("w", encoding="utf-8") as f:
            json.dump(record.to_json(), f, indent=2)
        return approval_path

    def revoke(self, proposal_id: str) -> None:
        path = self.approvals_dir / f"{proposal_id}.json"
        if path.exists():
            path.unlink()

    def active_versions(self) -> List[PromotionRecord]:
        records: List[PromotionRecord] = []
        for file in sorted(self.approvals_dir.glob("*.json")):
            payload = json.loads(file.read_text())
            records.append(
                PromotionRecord(
                    proposal_path=Path(payload["proposal"]),
                    approved_at=payload["approved_at"],
                    approved_by=payload.get("approved_by", "unknown"),
                    notes=payload.get("notes", ""),
                )
            )
        return records

    def _proposal_path(self, filename: str) -> Path:
        return self.proposals_dir / filename
