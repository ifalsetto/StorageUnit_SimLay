from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.database import db_session
from app.models.decision import DecisionInput
from app.models.practice import PracticeFlowResponse
from app.services.practice_flow import build_simlay_practice_flow

router = APIRouter(prefix="/api/practice", tags=["practice"])


@router.post("/simlay/{run_id}", response_model=PracticeFlowResponse)
def simlay_practice(run_id: str, payload: DecisionInput):
    """Render one real SimLay run as a FalseTech Practice vertical slice.

    This endpoint reuses SimLay's existing valuation/decision logic. It reports
    evidence and a recommended action, but intentionally does not claim the
    real-world action was executed, verified, or persisted to Outcome Memory.
    """

    with db_session() as conn:
        try:
            return build_simlay_practice_flow(conn, run_id, payload)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
