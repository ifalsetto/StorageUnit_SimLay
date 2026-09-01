from __future__ import annotations

from typing import Any

from app.core.database import row_to_dict
from app.models.decision import DecisionInput, DecisionVerdict
from app.models.practice import PracticeFlowResponse
from app.services.decision_engine import compute_decision


def _recommended_action(verdict: DecisionVerdict | str, safe_bid: float, max_bid: float) -> dict[str, Any]:
    verdict_value = verdict.value if isinstance(verdict, DecisionVerdict) else str(verdict)

    if verdict_value == DecisionVerdict.BUY.value:
        message = f"Proceed only with human approval and only while the bid remains at or below ${safe_bid:.2f}."
        ceiling = safe_bid
    elif verdict_value == DecisionVerdict.MAYBE.value:
        message = f"Manual review required. Do not exceed the hard maximum bid of ${max_bid:.2f}."
        ceiling = max_bid
    else:
        message = "Pass. Current evidence does not support buying this unit under the configured decision rules."
        ceiling = 0.0

    return {
        "recommended_action": message,
        "bid_ceiling": round(float(ceiling), 2),
        "human_authorization_required": True,
        "executed": False,
    }


def build_simlay_practice_flow(
    conn,
    run_id: str,
    inputs: DecisionInput | dict[str, Any],
) -> PracticeFlowResponse:
    if not isinstance(inputs, DecisionInput):
        inputs = DecisionInput(**inputs)

    run = row_to_dict(conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone())
    if not run:
        raise ValueError(f"Run not found: {run_id}")

    decision = compute_decision(conn, run_id, inputs)

    evidence_record_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM evidence e
        JOIN items i ON i.item_id = e.item_id
        WHERE i.run_id=? AND i.deleted_at IS NULL
        """,
        (run_id,),
    ).fetchone()[0]

    action = _recommended_action(decision.verdict, decision.safe_bid, decision.max_bid)

    return PracticeFlowResponse(
        run_id=run_id,
        real_input={
            "run_short": run.get("run_short"),
            "profile_name": run.get("profile_name"),
            "run_status": run.get("status"),
            "media_type": run.get("media_type"),
            "owner": run.get("owner") or "Unassigned",
            "current_bid": inputs.current_bid,
            "buyer_premium_pct": inputs.buyer_premium_pct,
            "tax_rate_pct": inputs.tax_rate_pct,
            "sell_through_pct": inputs.sell_through_pct,
            "risk_buffer_pct": inputs.risk_buffer_pct,
            "minimum_profit_dollars": inputs.minimum_profit_dollars,
            "target_roi_pct": inputs.target_roi_pct,
        },
        process=[
            "Reuse the existing SimLay run and normalized active inventory records.",
            "Apply existing valuation gates; Unknown-confidence items do not count as reliable upside.",
            "Exclude recoverably deleted inventory from evidence and acquisition-decision totals.",
            "Reuse the existing conservative SimLay decision engine to calculate safe bid, maximum bid, profit, and ROI.",
            "Translate the verdict into a human-authorized next action without auto-executing a purchase.",
        ],
        evidence={
            "source_system": "StorageUnit SimLay",
            "total_item_count": decision.total_item_count,
            "priced_item_count": decision.priced_item_count,
            "unknown_item_count": decision.unknown_item_count,
            "evidence_record_count": int(evidence_record_count),
            "projected_gross_resale": decision.projected_gross_resale,
            "projected_sell_through_cash": decision.projected_sell_through_cash,
            "warning_count": decision.warning_count,
            "warnings": decision.warnings,
            "notes": decision.notes,
        },
        decision={
            "verdict": decision.verdict,
            "safe_bid": decision.safe_bid,
            "max_bid": decision.max_bid,
            "current_bid": decision.current_bid,
            "estimated_total_cost": decision.estimated_total_cost,
            "estimated_profit": decision.estimated_profit,
            "estimated_roi_pct": decision.estimated_roi_pct,
            "labor_hours": decision.labor_hours,
            "labor_cost": decision.labor_cost,
            "risk_buffer": decision.risk_buffer,
        },
        action=action,
        result={
            "status": "decision_ready",
            "executed": False,
            "verified_outcome": False,
            "proof_recorded": False,
            "outcome_memory_persisted": False,
            "next_verification": (
                "After the real auction/action, record the actual purchase price, execution result, "
                "and realized resale outcome before promoting this run to verified proof/outcome memory."
            ),
        },
        provenance={
            "observed": [
                "Run metadata, active inventory counts, and active-item evidence count come from the SimLay SQLite data model.",
            ],
            "derived": [
                "Safe bid, maximum bid, projected cash, cost, profit, and ROI come from the existing SimLay decision engine.",
            ],
            "inferred": [
                "The recommended next action is a presentation-layer interpretation of the existing decision verdict.",
            ],
            "decision_engine": "app.services.decision_engine.compute_decision",
            "contract_version": "1.1",
        },
    )
