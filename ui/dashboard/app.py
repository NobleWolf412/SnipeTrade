"""FastAPI dashboard exposing live telemetry and control toggles."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from analysis.live_metrics import LiveMetricsStore
from snipetrade.adapt.calibration import summarize_proposals
from snipetrade.adapt.promoter import CalibrationPromoter

DATA_DIR = Path("data")
PROPOSALS_DIR = DATA_DIR / "calibration" / "proposals"
APPROVALS_DIR = DATA_DIR / "calibration" / "approvals"
METRICS_DB = DATA_DIR / "metrics.sqlite"


class OverrideRequest(BaseModel):
    action: str
    value: str | None = None


def create_app() -> FastAPI:
    app = FastAPI(title="SnipeTrade Mission Control")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    metrics_store = LiveMetricsStore(METRICS_DB)
    promoter = CalibrationPromoter(PROPOSALS_DIR, APPROVALS_DIR)

    @app.get("/metrics/live")
    def get_live_metrics() -> Dict[str, List[Dict[str, float]]]:
        data = metrics_store.fetch_recent(limit=500)
        return {"items": [row._asdict() for row in data.itertuples(index=False)]}

    @app.get("/calibration/proposals")
    def get_proposals():
        proposals = summarize_proposals(PROPOSALS_DIR)
        return [p.to_json() for p in proposals]

    @app.get("/calibration/pending")
    def get_pending():
        return [p.to_json() for p in promoter.pending()]

    @app.post("/calibration/approve/{proposal_id}")
    def approve_proposal(proposal_id: str, request: OverrideRequest):
        proposals = {p.proposal_id: p for p in summarize_proposals(PROPOSALS_DIR)}
        if proposal_id not in proposals:
            raise HTTPException(404, "proposal not found")
        promoter.approve(proposals[proposal_id], approver=request.value or "dashboard")
        return {"status": "ok"}

    @app.post("/overrides")
    def post_override(request: OverrideRequest):
        overrides_path = DATA_DIR / "overrides.json"
        overrides_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.loads(overrides_path.read_text()) if overrides_path.exists() else {}
        payload[request.action] = request.value
        overrides_path.write_text(json.dumps(payload, indent=2))
        return {"status": "ok"}

    return app
