from __future__ import annotations

from typing import Any

from app.core.database import rows_to_dicts
from app.models.decision import DecisionInput, DecisionResult, DecisionVerdict


def _money(value: float) -> float:
    return round(float(value), 2)


def estimate_labor_hours(inputs: DecisionInput, total_items: int, unknown_item_count: int) -> float:
    if inputs.labor_hours_override is not None:
        return float(inputs.labor_hours_override)

    base_hours = max(2.0, inputs.unit_size_sqft / 50.0)
    item_hours = total_items * 0.12
    unknown_penalty = unknown_item_count * 0.08
    ceiling_multiplier = 1.35 if inputs.packed_to_ceiling else 1.0
    helper_divisor = 1 + min(inputs.helpers, 4) * 0.35
    load_hours = inputs.vehicle_loads_estimate * 0.75

    return round(((base_hours + item_hours + unknown_penalty + load_hours) * ceiling_multiplier) / helper_divisor, 2)


def _verdict(current_bid: float, safe_bid: float, max_bid: float, estimated_profit: float, warnings: list[str]) -> DecisionVerdict:
    if current_bid <= safe_bid and estimated_profit > 0 and len(warnings) <= 2:
        return DecisionVerdict.BUY
    if current_bid <= max_bid and estimated_profit >= 0:
        return DecisionVerdict.MAYBE
    return DecisionVerdict.PASS


def compute_decision(conn, run_id: str, inputs: DecisionInput | dict[str, Any]) -> DecisionResult:
    if not isinstance(inputs, DecisionInput):
        inputs = DecisionInput(**inputs)

    run = conn.execute("SELECT run_id FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if not run:
        raise ValueError(f"Run not found: {run_id}")

    items = rows_to_dicts(conn.execute("SELECT * FROM items WHERE run_id=?", (run_id,)).fetchall())
    total_items = len(items)
    priced_items = [item for item in items if item.get("value_export") is not None and int(item.get("valuation_passed_gates") or 0) == 1]
    unknown_items = [item for item in items if item.get("confidence") == "Unknown"]
    warnings: list[str] = []
    notes: list[str] = []

    projected_gross = sum(float(item.get("value_export") or 0) * int(item.get("quantity") or 1) for item in priced_items)
    sell_through_cash = projected_gross * (inputs.sell_through_pct / 100.0)
    selling_fees = sell_through_cash * (inputs.selling_fee_pct / 100.0)
    labor_hours = estimate_labor_hours(inputs, total_items, len(unknown_items))
    labor_cost = labor_hours * inputs.labor_rate_per_hour
    bid_fees = inputs.current_bid * ((inputs.buyer_premium_pct + inputs.tax_rate_pct) / 100.0)
    risk_buffer = sell_through_cash * (inputs.risk_buffer_pct / 100.0)
    total_cost = inputs.current_bid + bid_fees + selling_fees + labor_cost + inputs.dump_fee_estimate + inputs.fuel_misc_estimate + risk_buffer
    estimated_profit = sell_through_cash - total_cost
    invested_cash = max(inputs.current_bid + bid_fees + inputs.dump_fee_estimate + inputs.fuel_misc_estimate + labor_cost, 1.0)
    roi_pct = (estimated_profit / invested_cash) * 100.0

    required_profit = max(inputs.minimum_profit_dollars, sell_through_cash * (inputs.target_roi_pct / 100.0))
    non_bid_costs = selling_fees + labor_cost + inputs.dump_fee_estimate + inputs.fuel_misc_estimate + risk_buffer
    bid_multiplier = 1 + ((inputs.buyer_premium_pct + inputs.tax_rate_pct) / 100.0)
    max_bid = max(0.0, (sell_through_cash - non_bid_costs - required_profit) / bid_multiplier)
    safe_bid = max(0.0, max_bid * 0.75)

    if total_items == 0:
        warnings.append("No inventory items found. Decision is based on zero visible item value.")
    if projected_gross <= 0:
        warnings.append("No priced inventory value passed valuation gates.")
    if len(unknown_items):
        warnings.append(f"{len(unknown_items)} item(s) are Unknown confidence and excluded from reliable upside.")
    if len(priced_items) < max(1, total_items // 2) and total_items > 0:
        warnings.append("Less than half of inventory has exportable valuation.")
    if inputs.packed_to_ceiling:
        notes.append("Packed-to-ceiling risk increased labor estimate.")
    if inputs.helpers > 0:
        notes.append("Helper count reduced labor estimate.")

    result_verdict = _verdict(inputs.current_bid, safe_bid, max_bid, estimated_profit, warnings)

    return DecisionResult(
        run_id=run_id,
        verdict=result_verdict,
        safe_bid=_money(safe_bid),
        max_bid=_money(max_bid),
        current_bid=_money(inputs.current_bid),
        projected_gross_resale=_money(projected_gross),
        projected_sell_through_cash=_money(sell_through_cash),
        estimated_total_cost=_money(total_cost),
        estimated_profit=_money(estimated_profit),
        estimated_roi_pct=round(roi_pct, 2),
        labor_hours=labor_hours,
        labor_cost=_money(labor_cost),
        dump_fee_estimate=_money(inputs.dump_fee_estimate),
        risk_buffer=_money(risk_buffer),
        unknown_item_count=len(unknown_items),
        priced_item_count=len(priced_items),
        total_item_count=total_items,
        warning_count=len(warnings),
        warnings=warnings,
        notes=notes,
    )
