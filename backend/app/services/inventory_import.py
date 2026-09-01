from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.database import row_to_dict, rows_to_dicts, to_json_text
from app.core.ids import new_uuid
from app.models.enums import Confidence, Condition, InventoryOwner, ItemAction, TruthSource
from app.services.normalization import choose_category, normalize_name

IMPORT_SOURCE_NAME = "FalseTech_SimLay_Photo_Inventory"


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _confidence(value: Any) -> str:
    text = str(value or "Unknown").strip().lower()
    if text == "verified":
        return Confidence.VERIFIED.value
    if text == "inferred":
        return Confidence.INFERRED.value
    return Confidence.UNKNOWN.value


def _source(value: Any) -> str:
    text = str(value or "").strip()
    lowered = text.lower()
    ordered = [
        ("web (cited)", TruthSource.WEB_CITED.value),
        ("approved comp", TruthSource.APPROVED_COMP.value),
        ("tony history", TruthSource.TONY_HISTORY.value),
        ("default library", TruthSource.DEFAULT_LIBRARY.value),
        ("user confirmed", TruthSource.USER_CONFIRMED.value),
        ("photo", TruthSource.PHOTO.value),
        ("user visual", TruthSource.USER_VISUAL.value),
        ("manual", TruthSource.MANUAL.value),
    ]
    for needle, canonical in ordered:
        if needle in lowered:
            return canonical
    return TruthSource.MANUAL.value


def _condition(value: Any) -> tuple[str, str | None]:
    text = str(value or "").strip()
    allowed = {member.value for member in Condition}
    if text in allowed:
        return text, None
    if not text:
        return Condition.UNKNOWN.value, None
    return Condition.UNKNOWN.value, text


def _action(value: Any) -> str:
    text = str(value or "Unassigned").strip()
    allowed = {member.value for member in ItemAction}
    return text if text in allowed else ItemAction.UNASSIGNED.value


def _owner(value: InventoryOwner | str) -> str:
    if isinstance(value, InventoryOwner):
        return value.value
    text = str(value or InventoryOwner.UNASSIGNED.value).strip()
    allowed = {member.value for member in InventoryOwner}
    return text if text in allowed else InventoryOwner.UNASSIGNED.value


def _payload_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        items = payload.get("items", [])
    elif isinstance(payload, list):
        items = payload
    else:
        raise ValueError("Inventory import must be a JSON object with an items array or a JSON array.")
    if not isinstance(items, list):
        raise ValueError("Inventory import items must be a JSON array.")
    return [item for item in items if isinstance(item, dict)]


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


def import_photo_inventory(
    conn,
    run_id: str,
    payload: Any,
    config: dict[str, Any],
    owner: InventoryOwner | str = InventoryOwner.UNASSIGNED,
    source_name: str = IMPORT_SOURCE_NAME,
    dry_run: bool = False,
) -> dict[str, Any]:
    run = row_to_dict(conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone())
    if not run:
        raise ValueError(f"Run not found: {run_id}")

    owner_value = _owner(owner)
    items = _payload_items(payload)
    existing_refs = {
        row["external_ref"]
        for row in rows_to_dicts(
            conn.execute(
                "SELECT external_ref FROM inventory_import_refs WHERE run_id=? AND source_name=?",
                (run_id, source_name),
            ).fetchall()
        )
    }

    current_order = conn.execute(
        "SELECT COUNT(*) AS c FROM items WHERE run_id=? AND deleted_at IS NULL", (run_id,)
    ).fetchone()["c"]

    planned: list[dict[str, Any]] = []
    skipped: list[str] = []
    invalid: list[dict[str, Any]] = []

    for index, incoming in enumerate(items, start=1):
        external_ref = str(incoming.get("item_id") or incoming.get("id") or f"row-{index:04d}").strip()
        if external_ref in existing_refs:
            skipped.append(external_ref)
            continue

        title = str(
            incoming.get("title")
            or incoming.get("final_name")
            or incoming.get("name")
            or ""
        ).strip()
        if not title:
            invalid.append({"external_ref": external_ref, "reason": "missing_title"})
            continue

        confidence = _confidence(incoming.get("confidence"))
        source = _source(incoming.get("source"))
        condition, original_condition = _condition(incoming.get("condition"))
        item_action = _action(incoming.get("item_action") or incoming.get("action"))
        low = _number(incoming.get("value_low") if "value_low" in incoming else incoming.get("manual_value_low"))
        expected = _number(
            incoming.get("value_expected")
            if "value_expected" in incoming
            else incoming.get("manual_value_expected")
        )
        high = _number(incoming.get("value_high") if "value_high" in incoming else incoming.get("manual_value_high"))
        asking = _number(incoming.get("list_price") if "list_price" in incoming else incoming.get("asking_price"))

        if low is not None and high is not None and high < low:
            invalid.append({"external_ref": external_ref, "reason": "value_high_below_value_low"})
            continue
        if expected is not None and low is not None and expected < low:
            invalid.append({"external_ref": external_ref, "reason": "value_expected_below_value_low"})
            continue
        if expected is not None and high is not None and expected > high:
            invalid.append({"external_ref": external_ref, "reason": "value_expected_above_value_high"})
            continue

        category, subcategory, sort_tier, collectible = choose_category(title, config.get("taxonomy", {}))
        notes = str(incoming.get("notes") or "").strip()
        if original_condition:
            condition_note = f"Imported original condition text: {original_condition}"
            notes = f"{notes}\n{condition_note}".strip()

        planned.append(
            {
                "external_ref": external_ref,
                "title": title,
                "raw_name": incoming.get("raw_name"),
                "brand": incoming.get("brand"),
                "category": incoming.get("category") or category,
                "subcategory": incoming.get("subcategory") or subcategory,
                "quantity": int(incoming.get("quantity") or 1),
                "condition": condition,
                "confidence": confidence,
                "confidence_reason": incoming.get("confidence_reason"),
                "source": source,
                "notes": notes or None,
                "owner": owner_value,
                "item_action": item_action,
                "value_low": low,
                "value_expected": expected,
                "value_high": high,
                "asking_price": asking,
                "photo": Path(str(incoming.get("photo") or "")).name or None,
                "source_url": str(incoming.get("source_url") or "").strip() or None,
                "sort_tier": sort_tier,
                "possible_collectible": bool(collectible),
            }
        )

    if dry_run:
        return {
            "run_id": run_id,
            "owner": owner_value,
            "source_name": source_name,
            "dry_run": True,
            "input_count": len(items),
            "would_create": len(planned),
            "already_imported": len(skipped),
            "invalid": invalid,
            "sample": planned[:10],
        }

    batch_id = new_uuid("import")
    created: list[str] = []
    photo_refs = 0
    evidence_refs = 0

    for offset, item in enumerate(planned, start=1):
        item_id = new_uuid("item")
        sort_order = int(current_order) + offset
        conn.execute(
            """
            INSERT INTO items(
                item_id, run_id, raw_name, final_name, normalized_name, brand, category, subcategory,
                quantity, visible_condition, confidence, confidence_reason, source, notes, owner, item_action,
                manual_value_low, manual_value_expected, manual_value_high, asking_price,
                detected_in_media, flag_unknown, flag_possible_collectible, sort_tier, sort_order
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item_id,
                run_id,
                item["raw_name"],
                item["title"],
                normalize_name(item["title"]),
                item["brand"],
                item["category"],
                item["subcategory"],
                item["quantity"],
                item["condition"],
                item["confidence"],
                item["confidence_reason"],
                item["source"],
                item["notes"],
                item["owner"],
                item["item_action"],
                item["value_low"],
                item["value_expected"],
                item["value_high"],
                item["asking_price"],
                to_json_text([]),
                1 if item["confidence"] == Confidence.UNKNOWN.value else 0,
                1 if item["possible_collectible"] else 0,
                item["sort_tier"],
                sort_order,
            ),
        )
        conn.execute(
            """
            INSERT INTO inventory_import_refs(
                import_ref_id, import_batch_id, run_id, item_id, source_name, external_ref, source_photo_name
            )
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_uuid("importref"),
                batch_id,
                run_id,
                item_id,
                source_name,
                item["external_ref"],
                item["photo"],
            ),
        )
        if item["photo"]:
            photo_refs += 1
        if item["source_url"]:
            conn.execute(
                """
                INSERT INTO evidence(
                    evidence_id, item_id, source_type, source_name, url, listing_type,
                    included_in_valuation, exclusion_reason, notes
                )
                VALUES(?, ?, 'url', 'imported_reference', ?, 'active', 0, 'reference_only', ?)
                """,
                (
                    new_uuid("evidence"),
                    item_id,
                    item["source_url"],
                    "Imported citation/reference only. It does not independently authenticate this physical item or establish a sold price.",
                ),
            )
            evidence_refs += 1
        conn.execute(
            """
            INSERT INTO audit_events(audit_id, run_id, entity_type, entity_id, action, payload)
            VALUES(?, ?, 'item', ?, 'import', ?)
            """,
            (
                new_uuid("audit"),
                run_id,
                item_id,
                to_json_text(
                    {
                        "import_batch_id": batch_id,
                        "source_name": source_name,
                        "external_ref": item["external_ref"],
                        "owner": owner_value,
                        "photo": item["photo"],
                    }
                ),
            ),
        )
        created.append(item_id)

    _refresh_run_totals(conn, run_id)
    return {
        "run_id": run_id,
        "owner": owner_value,
        "source_name": source_name,
        "dry_run": False,
        "import_batch_id": batch_id,
        "input_count": len(items),
        "created_count": len(created),
        "created_item_ids": created,
        "already_imported": len(skipped),
        "invalid": invalid,
        "photo_references_recorded": photo_refs,
        "citation_references_recorded": evidence_refs,
    }


def relink_imported_media(conn, run_id: str, source_name: str = IMPORT_SOURCE_NAME) -> dict[str, Any]:
    run = conn.execute("SELECT run_id FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if not run:
        raise ValueError(f"Run not found: {run_id}")

    refs = rows_to_dicts(
        conn.execute(
            """
            SELECT r.item_id, r.external_ref, r.source_photo_name, i.representative_image_id, i.detected_in_media
            FROM inventory_import_refs r
            JOIN items i ON i.item_id=r.item_id
            WHERE r.run_id=? AND r.source_name=? AND r.source_photo_name IS NOT NULL AND i.deleted_at IS NULL
            """,
            (run_id, source_name),
        ).fetchall()
    )
    media = rows_to_dicts(
        conn.execute("SELECT media_id, file_path FROM media_inputs WHERE run_id=?", (run_id,)).fetchall()
    )
    by_basename: dict[str, list[dict[str, Any]]] = {}
    for row in media:
        by_basename.setdefault(Path(row["file_path"]).name, []).append(row)

    linked = 0
    missing: list[str] = []
    ambiguous: list[dict[str, Any]] = []
    already_linked = 0

    for ref in refs:
        matches = by_basename.get(ref["source_photo_name"], [])
        if len(matches) == 0:
            missing.append(ref["external_ref"])
            continue
        if len(matches) > 1:
            ambiguous.append(
                {
                    "external_ref": ref["external_ref"],
                    "photo": ref["source_photo_name"],
                    "matches": [match["media_id"] for match in matches],
                }
            )
            continue

        media_id = matches[0]["media_id"]
        if ref.get("representative_image_id"):
            already_linked += 1
            continue
        try:
            detected = json.loads(ref.get("detected_in_media") or "[]")
        except (TypeError, json.JSONDecodeError):
            detected = []
        if media_id not in detected:
            detected.append(media_id)
        conn.execute(
            """
            UPDATE items
            SET representative_image_id=?, detected_in_media=?, updated_at=CURRENT_TIMESTAMP
            WHERE item_id=?
            """,
            (media_id, to_json_text(detected), ref["item_id"]),
        )
        conn.execute(
            """
            INSERT INTO audit_events(audit_id, run_id, entity_type, entity_id, action, payload)
            VALUES(?, ?, 'item', ?, 'media_relink', ?)
            """,
            (
                new_uuid("audit"),
                run_id,
                ref["item_id"],
                to_json_text(
                    {
                        "external_ref": ref["external_ref"],
                        "photo": ref["source_photo_name"],
                        "media_id": media_id,
                    }
                ),
            ),
        )
        linked += 1

    return {
        "run_id": run_id,
        "source_name": source_name,
        "references_checked": len(refs),
        "linked": linked,
        "already_linked": already_linked,
        "missing_count": len(missing),
        "missing_external_refs": missing,
        "ambiguous_count": len(ambiguous),
        "ambiguous": ambiguous,
    }
