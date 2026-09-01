from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.core.config import load_all_config
from app.core.database import db_session, row_to_dict, rows_to_dicts, to_json_text
from app.core.ids import new_uuid
from app.models.enums import InventoryOwner
from app.schemas import ItemCreate, ItemDuplicateRequest, ItemUpdate
from app.services.normalization import choose_category, normalize_name
from app.services.valuation import compute_item_valuation

router = APIRouter(prefix="/api/items", tags=["items"])


def _audit(conn, run_id: str | None, item_id: str, action: str, payload: dict[str, Any] | None = None) -> None:
    conn.execute(
        """
        INSERT INTO audit_events(audit_id, run_id, entity_type, entity_id, action, payload)
        VALUES(?, ?, 'item', ?, ?, ?)
        """,
        (new_uuid("audit"), run_id, item_id, action, to_json_text(payload or {})),
    )


def _refresh_run_totals(conn, run_id: str) -> None:
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS total_items,
            SUM(CASE WHEN confidence='Verified' THEN 1 ELSE 0 END) AS total_verified,
            SUM(CASE WHEN confidence='Inferred' THEN 1 ELSE 0 END) AS total_inferred,
            SUM(CASE WHEN confidence='Unknown' THEN 1 ELSE 0 END) AS total_unknown
        FROM items
        WHERE run_id=? AND deleted_at IS NULL
        """,
        (run_id,),
    ).fetchone()
    conn.execute(
        """
        UPDATE runs
        SET total_items=?, total_verified=?, total_inferred=?, total_unknown=?, updated_at=CURRENT_TIMESTAMP
        WHERE run_id=?
        """,
        (
            int(row["total_items"] or 0),
            int(row["total_verified"] or 0),
            int(row["total_inferred"] or 0),
            int(row["total_unknown"] or 0),
            run_id,
        ),
    )


def _validate_manual_band(data: dict[str, Any]) -> None:
    low = data.get("manual_value_low")
    expected = data.get("manual_value_expected")
    high = data.get("manual_value_high")
    if low is not None and high is not None and high < low:
        raise HTTPException(422, "manual_value_high must be greater than or equal to manual_value_low")
    if expected is not None and low is not None and expected < low:
        raise HTTPException(422, "manual_value_expected cannot be below manual_value_low")
    if expected is not None and high is not None and expected > high:
        raise HTTPException(422, "manual_value_expected cannot be above manual_value_high")


def _serialize_item(row: dict[str, Any]) -> dict[str, Any]:
    row["display_value_low"] = row.get("manual_value_low") if row.get("manual_value_low") is not None else row.get("value_p25")
    row["display_value_expected"] = (
        row.get("manual_value_expected")
        if row.get("manual_value_expected") is not None
        else (row.get("value_p50") if row.get("value_p50") is not None else row.get("value_export"))
    )
    row["display_value_high"] = row.get("manual_value_high") if row.get("manual_value_high") is not None else row.get("value_p75")
    return row


@router.post("")
def create_item(payload: ItemCreate):
    config = load_all_config()
    category, subcategory, sort_tier, collectible = choose_category(payload.final_name, config.get("taxonomy", {}))
    category = payload.category or category
    subcategory = payload.subcategory or subcategory
    item_id = new_uuid("item")
    with db_session() as conn:
        run = conn.execute("SELECT run_id FROM runs WHERE run_id=?", (payload.run_id,)).fetchone()
        if not run:
            raise HTTPException(404, "Run not found")
        current = conn.execute(
            "SELECT COUNT(*) c FROM items WHERE run_id=? AND deleted_at IS NULL", (payload.run_id,)
        ).fetchone()["c"]
        conn.execute(
            """
            INSERT INTO items(
                item_id, run_id, raw_name, final_name, normalized_name, brand, category, subcategory,
                quantity, visible_condition, confidence, confidence_reason, source, notes, owner, item_action,
                manual_value_low, manual_value_expected, manual_value_high, asking_price,
                representative_image_id, detected_in_media, flag_unknown, flag_possible_collectible, sort_tier, sort_order
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item_id,
                payload.run_id,
                payload.raw_name,
                payload.final_name,
                normalize_name(payload.final_name),
                payload.brand,
                category,
                subcategory,
                payload.quantity,
                payload.visible_condition,
                payload.confidence,
                payload.confidence_reason,
                payload.source,
                payload.notes,
                payload.owner,
                payload.item_action,
                payload.manual_value_low,
                payload.manual_value_expected,
                payload.manual_value_high,
                payload.asking_price,
                payload.representative_image_id,
                to_json_text([payload.representative_image_id] if payload.representative_image_id else []),
                1 if payload.confidence == "Unknown" else 0,
                1 if collectible else 0,
                sort_tier,
                current + 1,
            ),
        )
        _audit(
            conn,
            payload.run_id,
            item_id,
            "create",
            {"owner": payload.owner, "final_name": payload.final_name, "source": payload.source},
        )
        _refresh_run_totals(conn, payload.run_id)
    return {"item_id": item_id}


@router.get("/run/{run_id}/summary")
def inventory_summary(run_id: str):
    with db_session() as conn:
        run = conn.execute("SELECT run_id FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if not run:
            raise HTTPException(404, "Run not found")
        rows = rows_to_dicts(
            conn.execute(
                """
                SELECT owner, item_action, confidence, manual_value_low, manual_value_expected, manual_value_high,
                       asking_price, value_p25, value_p50, value_p75, value_export
                FROM items
                WHERE run_id=? AND deleted_at IS NULL
                """,
                (run_id,),
            ).fetchall()
        )

    owners = {
        owner.value: {
            "count": 0,
            "value_low": 0.0,
            "value_expected": 0.0,
            "value_high": 0.0,
            "asking_total": 0.0,
            "actions": {"Sell": 0, "Donate": 0, "Dump": 0, "Hold": 0, "Unassigned": 0},
            "confidence": {"Verified": 0, "Inferred": 0, "Unknown": 0},
        }
        for owner in InventoryOwner
    }
    for row in rows:
        owner_name = row.get("owner") or "Unassigned"
        if owner_name not in owners:
            owner_name = "Unassigned"
        bucket = owners[owner_name]
        bucket["count"] += 1
        low = row.get("manual_value_low") if row.get("manual_value_low") is not None else row.get("value_p25")
        expected = row.get("manual_value_expected") if row.get("manual_value_expected") is not None else (
            row.get("value_p50") if row.get("value_p50") is not None else row.get("value_export")
        )
        high = row.get("manual_value_high") if row.get("manual_value_high") is not None else row.get("value_p75")
        bucket["value_low"] += float(low or 0)
        bucket["value_expected"] += float(expected or 0)
        bucket["value_high"] += float(high or 0)
        bucket["asking_total"] += float(row.get("asking_price") or 0)
        action = row.get("item_action") or "Unassigned"
        bucket["actions"][action] = bucket["actions"].get(action, 0) + 1
        confidence = row.get("confidence") or "Unknown"
        bucket["confidence"][confidence] = bucket["confidence"].get(confidence, 0) + 1

    for bucket in owners.values():
        for key in ("value_low", "value_expected", "value_high", "asking_total"):
            bucket[key] = round(bucket[key], 2)
    return {"run_id": run_id, "owners": owners, "total_count": len(rows)}


@router.get("/{run_id}")
def list_items(
    run_id: str,
    owner: InventoryOwner | None = None,
    include_deleted: bool = Query(default=False),
):
    where = ["run_id=?"]
    values: list[Any] = [run_id]
    if owner is not None:
        where.append("owner=?")
        values.append(owner.value if isinstance(owner, InventoryOwner) else str(owner))
    if not include_deleted:
        where.append("deleted_at IS NULL")
    sql = f"SELECT * FROM items WHERE {' AND '.join(where)} ORDER BY sort_tier, sort_order, final_name"
    with db_session() as conn:
        rows = rows_to_dicts(conn.execute(sql, values).fetchall())
    return {"items": [_serialize_item(row) for row in rows]}


@router.get("/detail/{item_id}")
def get_item(item_id: str):
    with db_session() as conn:
        item = row_to_dict(conn.execute("SELECT * FROM items WHERE item_id=?", (item_id,)).fetchone())
        if not item:
            raise HTTPException(404, "Item not found")
        item["evidence"] = rows_to_dicts(conn.execute("SELECT * FROM evidence WHERE item_id=?", (item_id,)).fetchall())
        media_ids = []
        try:
            import json
            media_ids = json.loads(item.get("detected_in_media") or "[]")
        except (TypeError, ValueError):
            media_ids = []
        if item.get("representative_image_id") and item["representative_image_id"] not in media_ids:
            media_ids.insert(0, item["representative_image_id"])
        item["media"] = []
        if media_ids:
            placeholders = ",".join("?" for _ in media_ids)
            item["media"] = rows_to_dicts(
                conn.execute(f"SELECT * FROM media_inputs WHERE media_id IN ({placeholders})", media_ids).fetchall()
            )
    return _serialize_item(item)


@router.patch("/{item_id}")
def update_item(item_id: str, payload: ItemUpdate):
    data = payload.model_dump(exclude_unset=True)
    if not data:
        return {"updated": False}
    if "final_name" in data:
        data["normalized_name"] = normalize_name(data["final_name"])
    with db_session() as conn:
        current = row_to_dict(conn.execute("SELECT * FROM items WHERE item_id=?", (item_id,)).fetchone())
        if not current:
            raise HTTPException(404, "Item not found")
        merged = dict(current)
        merged.update(data)
        _validate_manual_band(merged)
        if "confidence" in data:
            data["flag_unknown"] = 1 if data["confidence"] == "Unknown" else 0
        assignments = ", ".join([f"{k}=?" for k in data.keys()])
        values = list(data.values()) + [item_id]
        conn.execute(f"UPDATE items SET {assignments}, updated_at=CURRENT_TIMESTAMP WHERE item_id=?", values)
        _audit(conn, current["run_id"], item_id, "update", {"changes": data})
        _refresh_run_totals(conn, current["run_id"])
    return {"updated": True}


@router.delete("/{item_id}")
def delete_item(
    item_id: str,
    confirm: bool = Query(default=False),
    reason: str | None = Query(default=None, max_length=200),
):
    if not confirm:
        raise HTTPException(400, "Delete requires confirm=true. SimLay uses recoverable soft deletion.")
    with db_session() as conn:
        item = row_to_dict(conn.execute("SELECT * FROM items WHERE item_id=?", (item_id,)).fetchone())
        if not item:
            raise HTTPException(404, "Item not found")
        if item.get("deleted_at"):
            return {"deleted": True, "already_deleted": True, "recoverable": True}
        conn.execute(
            "UPDATE items SET deleted_at=CURRENT_TIMESTAMP, deleted_reason=?, updated_at=CURRENT_TIMESTAMP WHERE item_id=?",
            (reason, item_id),
        )
        _audit(conn, item["run_id"], item_id, "remove", {"reason": reason, "recoverable": True})
        _refresh_run_totals(conn, item["run_id"])
    return {"deleted": True, "recoverable": True}


@router.post("/{item_id}/restore")
def restore_item(item_id: str):
    with db_session() as conn:
        item = row_to_dict(conn.execute("SELECT * FROM items WHERE item_id=?", (item_id,)).fetchone())
        if not item:
            raise HTTPException(404, "Item not found")
        conn.execute(
            "UPDATE items SET deleted_at=NULL, deleted_reason=NULL, updated_at=CURRENT_TIMESTAMP WHERE item_id=?",
            (item_id,),
        )
        _audit(conn, item["run_id"], item_id, "restore", {})
        _refresh_run_totals(conn, item["run_id"])
    return {"restored": True}


@router.post("/{item_id}/duplicate")
def duplicate_item(item_id: str, payload: ItemDuplicateRequest | None = None):
    payload = payload or ItemDuplicateRequest()
    with db_session() as conn:
        item = row_to_dict(conn.execute("SELECT * FROM items WHERE item_id=?", (item_id,)).fetchone())
        if not item:
            raise HTTPException(404, "Item not found")
        new_id = new_uuid("item")
        owner = payload.owner or item.get("owner") or "Unassigned"
        columns = [
            "run_id", "raw_name", "final_name", "normalized_name", "brand", "category", "subcategory", "quantity",
            "visible_condition", "confidence", "confidence_reason", "source", "notes", "owner", "item_action",
            "manual_value_low", "manual_value_expected", "manual_value_high", "asking_price", "representative_image_id",
            "detected_in_media", "flag_unknown", "flag_missing_comps", "flag_high_variance", "flag_possible_collectible",
            "sort_tier", "sort_order", "value_p25", "value_p50", "value_p75", "value_export", "value_source",
            "valuation_passed_gates",
        ]
        values = [item.get(column) for column in columns]
        values[columns.index("owner")] = owner
        values[columns.index("final_name")] = f"{item.get('final_name') or 'Item'} (copy)"
        values[columns.index("normalized_name")] = normalize_name(values[columns.index("final_name")])
        placeholders = ", ".join("?" for _ in columns)
        conn.execute(
            f"INSERT INTO items(item_id, {', '.join(columns)}, flag_duplicate_suspect, wix_exported) VALUES(?, {placeholders}, 1, 0)",
            [new_id] + values,
        )
        _audit(conn, item["run_id"], new_id, "duplicate", {"source_item_id": item_id, "owner": owner})
        _refresh_run_totals(conn, item["run_id"])
    return {"item_id": new_id, "duplicated_from": item_id}


@router.post("/{item_id}/value")
def value_item(item_id: str):
    config = load_all_config()
    with db_session() as conn:
        result = compute_item_valuation(conn, item_id, config)
        item = conn.execute("SELECT run_id FROM items WHERE item_id=?", (item_id,)).fetchone()
        if item:
            _audit(conn, item["run_id"], item_id, "value", {"result": result})
    return result
