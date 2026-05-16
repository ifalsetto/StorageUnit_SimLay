from fastapi import APIRouter, HTTPException

from app.core.config import load_all_config
from app.core.database import db_session, rows_to_dicts, row_to_dict, to_json_text
from app.core.ids import new_uuid
from app.schemas import ItemCreate, ItemUpdate
from app.services.normalization import normalize_name, choose_category
from app.services.valuation import compute_item_valuation

router = APIRouter(prefix="/api/items", tags=["items"])

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
        current = conn.execute("SELECT COUNT(*) c FROM items WHERE run_id=?", (payload.run_id,)).fetchone()["c"]
        conn.execute("""
            INSERT INTO items(item_id, run_id, raw_name, final_name, normalized_name, brand, category, subcategory,
            quantity, visible_condition, confidence, confidence_reason, source, notes, representative_image_id,
            detected_in_media, flag_unknown, flag_possible_collectible, sort_tier, sort_order)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (item_id, payload.run_id, payload.raw_name, payload.final_name, normalize_name(payload.final_name), payload.brand,
              category, subcategory, payload.quantity, payload.visible_condition, payload.confidence, payload.confidence_reason,
              payload.source, payload.notes, payload.representative_image_id, to_json_text([payload.representative_image_id] if payload.representative_image_id else []),
              1 if payload.confidence == "Unknown" else 0, 1 if collectible else 0, sort_tier, current + 1))
        conn.execute("UPDATE runs SET total_items=(SELECT COUNT(*) FROM items WHERE run_id=?) WHERE run_id=?", (payload.run_id, payload.run_id))
    return {"item_id": item_id}

@router.get("/{run_id}")
def list_items(run_id: str):
    with db_session() as conn:
        rows = rows_to_dicts(conn.execute("SELECT * FROM items WHERE run_id=? ORDER BY sort_tier, sort_order, final_name", (run_id,)).fetchall())
    return {"items": rows}

@router.get("/detail/{item_id}")
def get_item(item_id: str):
    with db_session() as conn:
        item = row_to_dict(conn.execute("SELECT * FROM items WHERE item_id=?", (item_id,)).fetchone())
        if not item:
            raise HTTPException(404, "Item not found")
        item["evidence"] = rows_to_dicts(conn.execute("SELECT * FROM evidence WHERE item_id=?", (item_id,)).fetchall())
    return item

@router.patch("/{item_id}")
def update_item(item_id: str, payload: ItemUpdate):
    data = payload.model_dump(exclude_unset=True)
    if not data:
        return {"updated": False}
    if "final_name" in data:
        data["normalized_name"] = normalize_name(data["final_name"])
    assignments = ", ".join([f"{k}=?" for k in data.keys()])
    values = list(data.values()) + [item_id]
    with db_session() as conn:
        conn.execute(f"UPDATE items SET {assignments}, updated_at=CURRENT_TIMESTAMP WHERE item_id=?", values)
        if conn.total_changes == 0:
            raise HTTPException(404, "Item not found")
    return {"updated": True}

@router.post("/{item_id}/value")
def value_item(item_id: str):
    config = load_all_config()
    with db_session() as conn:
        result = compute_item_valuation(conn, item_id, config)
    return result
