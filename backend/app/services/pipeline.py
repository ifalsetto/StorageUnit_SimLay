import json
from pathlib import Path
from typing import Any

from app.core.database import from_json_text, rows_to_dicts, to_json_text
from app.core.ids import new_uuid
from app.services.dedupe import dedupe_items
from app.services.normalization import choose_category, normalize_name
from app.services.vision.factory import get_vision_provider
from app.services.valuation import compute_run_valuations

ALLOWED_CONFIDENCE = {"Verified", "Inferred", "Unknown"}
ALLOWED_CONDITION = {"New", "Like New", "Used", "Fair", "Parts", "Unknown"}


def validate_item_payload(item: dict[str, Any]) -> dict[str, Any]:
    final_name = (item.get("final_name") or item.get("raw_name") or "").strip()
    if not final_name:
        raise ValueError("Vision item missing name")
    confidence = item.get("confidence") or "Unknown"
    condition = item.get("visible_condition") or "Unknown"
    if confidence not in ALLOWED_CONFIDENCE:
        confidence = "Unknown"
    if condition not in ALLOWED_CONDITION:
        condition = "Unknown"
    item["final_name"] = final_name
    item["raw_name"] = item.get("raw_name") or final_name
    item["confidence"] = confidence
    item["visible_condition"] = condition
    item["quantity"] = int(item.get("quantity") or 1)
    item["source"] = item.get("source") or "User Visual"
    return item


async def process_run(conn, run_id: str, config: dict[str, Any], provider_name: str | None = None) -> dict[str, Any]:
    run = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if not run:
        raise ValueError(f"Run not found: {run_id}")
    media = rows_to_dicts(conn.execute("SELECT * FROM media_inputs WHERE run_id=? ORDER BY sequence_order", (run_id,)).fetchall())
    if not media:
        raise ValueError("No media uploaded for run")

    conn.execute("UPDATE runs SET status='processing' WHERE run_id=?", (run_id,))
    provider = get_vision_provider(config, provider_name=provider_name)
    all_raw: list[dict[str, Any]] = []
    warnings: list[str] = []
    for m in media:
        path = Path(__file__).resolve().parents[2] / m["file_path"]
        try:
            detected = await provider.detect_items(path)
            conn.execute("UPDATE media_inputs SET processed_at=CURRENT_TIMESTAMP, vision_response=? WHERE media_id=?", (to_json_text(detected), m["media_id"]))
            for obj in detected:
                obj = validate_item_payload(obj)
                obj["detected_in_media"] = [m["media_id"]]
                obj["representative_image_id"] = m["media_id"]
                all_raw.append(obj)
        except Exception as exc:
            warnings.append(f"Media {m['media_id']} failed vision processing: {exc}")
            conn.execute("UPDATE media_inputs SET processed_at=CURRENT_TIMESTAMP, vision_response=? WHERE media_id=?", (to_json_text({"error": str(exc)}), m["media_id"]))

    if not all_raw:
        conn.execute("UPDATE runs SET status='failed', errors=? WHERE run_id=?", (to_json_text(["No items detected"]), run_id))
        return {"status": "failed", "items_created": 0, "warnings": warnings}

    threshold = float(config.get("dedupe_rules", {}).get("strategies", {}).get("name_matching", {}).get("threshold", 0.90))
    deduped = dedupe_items(all_raw, threshold=threshold)
    for idx, item in enumerate(deduped, start=1):
        item_id = new_uuid("item")
        normalized = normalize_name(item["final_name"])
        category, subcategory, sort_tier, collectible = choose_category(item["final_name"], config.get("taxonomy", {}))
        if item.get("category"):
            category = item["category"]
        flags = item.get("flags", [])
        flag_unknown = 1 if item["confidence"] == "Unknown" else 0
        flag_duplicate = 1 if "duplicate_suspect" in flags else 0
        conn.execute("""
            INSERT INTO items(
                item_id, run_id, raw_name, final_name, normalized_name, brand, category, subcategory,
                quantity, visible_condition, confidence, confidence_reason, source, notes,
                representative_image_id, detected_in_media, flag_unknown, flag_duplicate_suspect,
                flag_possible_collectible, sort_tier, sort_order
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item_id, run_id, item.get("raw_name"), item.get("final_name"), normalized, item.get("brand"),
            category, subcategory, item.get("quantity", 1), item.get("visible_condition", "Unknown"),
            item.get("confidence"), item.get("confidence_reason"), item.get("source", "User Visual"), item.get("notes"),
            item.get("representative_image_id"), to_json_text(item.get("detected_in_media", [])), flag_unknown,
            flag_duplicate, 1 if collectible else 0, sort_tier, idx
        ))

    compute_run_valuations(conn, run_id, config)
    counts = conn.execute("""
        SELECT COUNT(*) total,
               SUM(CASE WHEN confidence='Verified' THEN 1 ELSE 0 END) verified,
               SUM(CASE WHEN confidence='Inferred' THEN 1 ELSE 0 END) inferred,
               SUM(CASE WHEN confidence='Unknown' THEN 1 ELSE 0 END) unknown
        FROM items WHERE run_id=?
    """, (run_id,)).fetchone()
    conn.execute("""
        UPDATE runs SET status='processed', total_items=?, total_verified=?, total_inferred=?, total_unknown=?, warnings=? WHERE run_id=?
    """, (counts["total"] or 0, counts["verified"] or 0, counts["inferred"] or 0, counts["unknown"] or 0, to_json_text(warnings), run_id))
    return {"status": "processed", "items_created": len(deduped), "warnings": warnings}
