from __future__ import annotations

from typing import Any

from pydantic import Field

from .base import SimLayModel


class PracticeFlowResponse(SimLayModel):
    """Portable FalseTech Practice contract for a real SimLay decision run.

    The contract intentionally separates observed/derived evidence from the
    recommendation and from any later real-world outcome. It does not claim an
    action was executed or an outcome was verified when SimLay only produced a
    decision.
    """

    capability: str = "simlay.storage_unit_decision"
    run_id: str
    pattern: list[str] = Field(
        default_factory=lambda: [
            "REAL INPUT",
            "FALSETECH PROCESS",
            "EVIDENCE",
            "DECISION",
            "ACTION",
            "RESULT",
        ]
    )
    real_input: dict[str, Any]
    process: list[str]
    evidence: dict[str, Any]
    decision: dict[str, Any]
    action: dict[str, Any]
    result: dict[str, Any]
    provenance: dict[str, Any]
