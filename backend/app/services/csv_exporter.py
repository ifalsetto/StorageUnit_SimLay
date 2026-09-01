import csv
import json
from pathlib import Path
from typing import Any

from app.core.database import rows_to_dicts, to_json_text
from app.core.ids import generate_handle, generate_sku
from app.models.exports import DEFAULT_WIX_EXPORT_POLICY


def _render_template(template: str, item: dict[str, Any], fallback: str) -> str:
    try:
        return template.format(**{k: (v if v is not None else "") for k, v in item.items()}).strip() or fallback
    except Exception:
        return fallback


def _condition_ok(condition: str | None, item: dict[str, Any]) -> bool:
    if not condition:
        return True
    if "confidence" in condition and "Verified" in condition:
        return item.get("confidence") == "Verified"
    return True


class WixCsvExporter:
    def __init__(self, config: dict[str, Any], exports_dir: Path):
        self.config = config
        self.schema = config["wix_schema"]
        self.exports_dir = exports_dir
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        self.headers = list(self.schema["required_headers"])
        self.price_policy = DEFAULT_WIX_EXPORT_POLICY

    def validate_headers(self, headers: list[str] | None = None) -> None:
        actual = headers or self.headers
        expected = list(self.schema["required_headers"])
        if len(actual) != len(expected):
            raise ValueError(f"Header count mismatch: got {len(actual)}, expected {len(expected)}")
        for i, (a, e) in enumerate(zip(actual, expected)):
            if a != e:
                raise ValueError(f"Header mismatch at position {i}: got {a!r}, expected {e!r}")

    def ensure_ids(self, conn, run: dict[str, Any], items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        export_cfg = self.config["app_config"].get("export", {})
        handle_prefix = export_cfg.get("handle_prefix", "ITEM")
        sku_prefix = export_cfg.get("sku_prefix", "FT-GEN")
        width = int(export_cfg.get("sequence_padding", 3))
        for seq, item in enumerate(items, start=1):
            expected_handle = generate_handle(run["run_short"], seq, handle_prefix, width)
            expected_sku = generate_sku(run["run_short"], seq, sku_prefix, width)
            if item.get("wix_handle") != expected_handle or item.get("wix_sku") != expected_sku or item.get("sort_order") != seq:
                conn.execute("UPDATE items SET wix_handle=?, wix_sku=?, sort_order=? WHERE item_id=?", (expected_handle, expected_sku, seq, item["item_id"]))
                item["wix_handle"] = expected_handle
                item["wix_sku"] = expected_sku
                item["sort_order"] = seq
        return items

    def item_to_row(self, item: dict[str, Any]) -> dict[str, str]:
        row = {h: self.schema.get("defaults", {}).get(h, "") for h in self.headers}
        for header, mapping in self.schema.get("field_mappings", {}).items():
            if header not in row:
                continue
            if not _condition_ok(mapping.get("condition"), item):
                row[header] = ""
                continue
            source = mapping.get("source")
            if source == "constant":
                value = mapping.get("value", "")
            elif source == "template":
                value = _render_template(mapping.get("template", ""), item, mapping.get("fallback", ""))
            else:
                value = item.get(source)
            if header == "Price":
                value = self.price_policy.price_value_or_blank(item, value)
            if value is None:
                value = ""
            fmt = mapping.get("format")
            if fmt and value != "":
                try:
                    value = fmt.format(float(value))
                except Exception:
                    value = ""
            row[header] = str(value)
        return row

    def export(self, conn, run_id: str) -> dict[str, Any]:
        run = dict(conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone() or {})
        if not run:
            raise ValueError(f"Run not found: {run_id}")
        items = rows_to_dicts(conn.execute(
            "SELECT * FROM items WHERE run_id=? AND deleted_at IS NULL ORDER BY sort_tier ASC, sort_order ASC, final_name ASC",
            (run_id,),
        ).fetchall())
        if not items:
            raise ValueError("No active items to export")
        self.validate_headers()
        items = self.ensure_ids(conn, run, items)
        rows = [self.item_to_row(item) for item in items]
        for row in rows:
            if not row.get("handle") or not row.get("Name") or not row.get("SKU (auto)"):
                raise ValueError("Required Wix field missing in generated row")
            if row.get("fieldType") != "PRODUCT":
                raise ValueError("Only PRODUCT rows are supported in MVP")
        path = self.exports_dir / f"{run['run_short']}_wix_inventory.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.headers, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        export_id = f"export_{run['run_short']}_csv"
        conn.execute("""
            INSERT OR REPLACE INTO exports(export_id, run_id, export_type, file_path, row_count, validation_passed, validation_errors)
            VALUES(?, ?, 'wix_csv', ?, ?, 1, ?)
        """, (export_id, run_id, str(path.relative_to(path.parents[1])), len(rows), to_json_text([])))
        conn.execute("UPDATE items SET wix_exported=1 WHERE run_id=? AND deleted_at IS NULL", (run_id,))
        conn.execute("UPDATE runs SET csv_exported_at=CURRENT_TIMESTAMP, status='completed' WHERE run_id=?", (run_id,))
        return {"export_id": export_id, "file_path": str(path), "row_count": len(rows), "validation_passed": True}
