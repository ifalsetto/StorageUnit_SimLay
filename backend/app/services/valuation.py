import math
from statistics import median
from typing import Any

from app.core.database import db_session, rows_to_dicts


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    if len(values) == 1:
        return float(values[0])
    k = (len(values) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(values[int(k)])
    return float(values[f] * (c - k) + values[c] * (k - f))


def remove_iqr_outliers(values: list[float], multiplier: float = 1.5) -> list[float]:
    if len(values) < 4:
        return values
    q1 = percentile(values, 25) or 0
    q3 = percentile(values, 75) or 0
    iqr = q3 - q1
    lower = q1 - multiplier * iqr
    upper = q3 + multiplier * iqr
    return [v for v in values if lower <= v <= upper]


def apply_condition_adjustment(value: float | None, condition: str, config: dict[str, Any]) -> float | None:
    if value is None:
        return None
    rules = config["valuation_rules"]
    behavior = rules.get("unknown_condition_behavior", "no_adjust")
    multipliers = rules.get("condition_multipliers", {})
    if condition == "Unknown":
        if behavior == "no_adjust":
            return value
        if behavior == "blank_value":
            return None
        if behavior == "default_used":
            return value * 0.70
        return value
    multiplier = multipliers.get(condition, 1.0)
    if multiplier is None:
        return None
    return value * float(multiplier)


def _mark_excluded(conn, evidence_id: str, reason: str) -> None:
    conn.execute(
        "UPDATE evidence SET included_in_valuation=0, exclusion_reason=? WHERE evidence_id=?",
        (reason, evidence_id),
    )


def gather_valid_evidence(conn, item_id: str, config: dict[str, Any]) -> tuple[list[dict], list[dict], list[str]]:
    rows = rows_to_dicts(conn.execute("SELECT * FROM evidence WHERE item_id=?", (item_id,)).fetchall())
    sold: list[dict] = []
    active: list[dict] = []
    warnings: list[str] = []
    discount_pct = float(config["app_config"]["evidence"].get("active_listing_discount_pct", 15))
    for ev in rows:
        if ev.get("price") is None:
            _mark_excluded(conn, ev["evidence_id"], "price_null")
            warnings.append(f"Evidence {ev['evidence_id']} excluded: price_null")
            continue
        if ev.get("refresh_status") in {"blocked", "gone"}:
            reason = f"refresh_{ev.get('refresh_status')}"
            _mark_excluded(conn, ev["evidence_id"], reason)
            warnings.append(f"Evidence {ev['evidence_id']} excluded: {reason}")
            continue
        if int(ev.get("is_bundle") or 0) == 1:
            _mark_excluded(conn, ev["evidence_id"], "bundle")
            continue
        price = float(ev["price"])
        if ev.get("listing_type") == "active" or int(ev.get("is_active_listing") or 0) == 1:
            ev["discounted_price"] = round(price * (1 - discount_pct / 100), 2)
            conn.execute("UPDATE evidence SET discounted_price=? WHERE evidence_id=?", (ev["discounted_price"], ev["evidence_id"]))
            active.append(ev)
        else:
            sold.append(ev)
        conn.execute("UPDATE evidence SET included_in_valuation=1, exclusion_reason=NULL WHERE evidence_id=?", (ev["evidence_id"],))
    return sold, active, warnings


def compute_item_valuation(conn, item_id: str, config: dict[str, Any]) -> dict[str, Any]:
    item = conn.execute("SELECT * FROM items WHERE item_id=?", (item_id,)).fetchone()
    if not item:
        raise ValueError(f"Item not found: {item_id}")
    item = dict(item)
    warnings: list[str] = []
    sold, active, ev_warnings = gather_valid_evidence(conn, item_id, config)
    warnings.extend(ev_warnings)
    rules = config["valuation_rules"]
    gates = rules.get("evidence_gates", {})
    min_comps = int(gates.get("min_comps", 3))
    max_variance = float(gates.get("max_variance_ratio", 4.0))
    active_rules = rules.get("evidence_types", {}).get("active_listings", {})
    fallback = rules.get("fallback_rules", {}).get("no_sold_comps", {})

    source_used = "sold"
    values = [float(ev["price"]) for ev in sold]
    if not values and active_rules.get("allowed", True) and fallback.get("use_active", True):
        min_active = int(active_rules.get("min_active_for_fallback", 5))
        active_values = [float(ev.get("discounted_price") or ev["price"]) for ev in active]
        if len(active_values) >= min_active:
            values = active_values
            source_used = "active_discounted_fallback"
        elif active_values:
            warnings.append(f"Active comps available ({len(active_values)}) but below active fallback minimum ({min_active})")

    if item.get("confidence") == "Unknown":
        conn.execute("""
            UPDATE items SET value_p25=NULL, value_p50=NULL, value_p75=NULL, value_export=NULL,
            value_source='none_unknown_confidence', valuation_passed_gates=0, flag_missing_comps=1 WHERE item_id=?
        """, (item_id,))
        return {"passed": False, "reason": "unknown_confidence", "warnings": warnings}

    if len(values) < min_comps:
        conn.execute("""
            UPDATE items SET value_p25=NULL, value_p50=NULL, value_p75=NULL, value_export=NULL,
            value_source='none_insufficient_evidence', valuation_passed_gates=0, flag_missing_comps=1 WHERE item_id=?
        """, (item_id,))
        return {"passed": False, "reason": "insufficient_evidence", "warnings": warnings, "valid_comp_count": len(values)}

    filtered = remove_iqr_outliers(values, float(rules.get("outlier_detection", {}).get("iqr_multiplier", 1.5))) if rules.get("outlier_detection", {}).get("enabled", True) else values
    if not filtered:
        filtered = values
    low, high = min(filtered), max(filtered)
    if low > 0 and high / low > max_variance:
        conn.execute("UPDATE items SET value_export=NULL, valuation_passed_gates=0, flag_high_variance=1 WHERE item_id=?", (item_id,))
        return {"passed": False, "reason": "high_variance", "warnings": warnings, "variance_ratio": high / low}

    p25 = percentile(filtered, 25)
    p50 = percentile(filtered, 50)
    p75 = percentile(filtered, 75)
    conf = item.get("confidence", "Inferred")
    method = rules.get("confidence_methods", {}).get(conf, {})
    export_percentile = float(method.get("percentile", 25))
    if source_used == "active_discounted_fallback":
        export_percentile = float(fallback.get("active_percentile", 20))
    export_value = percentile(filtered, export_percentile)
    if method.get("condition_adjustment", False):
        export_value = apply_condition_adjustment(export_value, item.get("visible_condition") or "Unknown", config)
    round_to = int(rules.get("export", {}).get("round_to", 0))
    if export_value is not None:
        export_value = round(export_value, round_to)
    value_source = f"{source_used}_p{int(export_percentile)}"
    conn.execute("""
        UPDATE items SET value_p25=?, value_p50=?, value_p75=?, value_export=?, value_source=?,
        valuation_passed_gates=1, flag_missing_comps=0, flag_high_variance=0 WHERE item_id=?
    """, (p25, p50, p75, export_value, value_source, item_id))
    return {"passed": True, "value_export": export_value, "value_source": value_source, "p25": p25, "p50": p50, "p75": p75, "warnings": warnings}


def compute_run_valuations(conn, run_id: str, config: dict[str, Any]) -> list[dict[str, Any]]:
    items = rows_to_dicts(conn.execute("SELECT item_id FROM items WHERE run_id=?", (run_id,)).fetchall())
    return [compute_item_valuation(conn, item["item_id"], config) for item in items]
