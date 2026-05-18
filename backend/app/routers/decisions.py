from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.database import db_session
from app.models.decision import DecisionInput
from app.services.decision_engine import compute_decision

router = APIRouter(prefix="/api/decisions", tags=["decisions"])


@router.post("/{run_id}")
def decide_run(run_id: str, payload: DecisionInput):
    with db_session() as conn:
        try:
            return compute_decision(conn, run_id, payload).model_dump()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
