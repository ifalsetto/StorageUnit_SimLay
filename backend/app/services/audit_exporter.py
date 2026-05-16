import json
from pathlib import Path
from typing import Any

from app.core.database import rows_to_dicts, from_json_text, to_json_text


def export_audit_json(conn, run_id: str, config: dict[str, Any], exports_dir: Path) -> dict[str, Any]:
    exports_dir.mkdir(parents=True, exist_ok=True)
    run = dict(conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone() or {})
    if not run:
        raise ValueError(f"Run not found: {run_id}")
    media = rows_to_dicts(conn.execute("SELECT * FROM media_inputs WHERE run_id=? ORDER BY sequence_order", (run_id,)).fetchall())
    items = rows_to_dicts(conn.execute("SELECT * FROM items WHERE run_id=? ORDER BY sort_tier, sort_order, final_name", (run_id,)).fetchall())
    for item in items:
        item["detected_in_media"] = from_json_text(item.get("detected_in_media"), [])
        item["evidence"] = rows_to_dicts(conn.execute("SELECT * FROM evidence WHERE item_id=?", (item["item_id"],)).fetchall())
    doc = {
        "run": {**run, "profile_snapshot": from_json_text(run.get("profile_snapshot"), {})},
        "config_snapshot": from_json_text(run.get("profile_snapshot"), {}),
        "media_inputs": media,
        "items": items,
        "errors": from_json_text(run.get("errors"), []),
        "warnings": from_json_text(run.get("warnings"), []),
    }
    path = exports_dir / f"{run['run_short']}_audit.json"
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    export_id = f"export_{run['run_short']}_audit"
    conn.execute("""
        INSERT OR REPLACE INTO exports(export_id, run_id, export_type, file_path, row_count, validation_passed, validation_errors)
        VALUES(?, ?, 'audit_json', ?, ?, 1, ?)
    """, (export_id, run_id, str(path), len(items), to_json_text([])))
    conn.execute("UPDATE runs SET audit_exported_at=CURRENT_TIMESTAMP WHERE run_id=?", (run_id,))
    return {"export_id": export_id, "file_path": str(path), "row_count": len(items), "validation_passed": True}
