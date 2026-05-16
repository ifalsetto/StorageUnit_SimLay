import csv
from pathlib import Path

from app.core.config import load_all_config
from app.core.database import init_db, connect, to_json_text
from app.core.ids import generate_handle, generate_sku
from app.services.csv_exporter import WixCsvExporter
from app.services.valuation import compute_run_valuations


def test_end_to_end_manual_evidence_to_wix_csv(tmp_path: Path):
    db = tmp_path / "simlay.db"
    init_db(db)
    config = load_all_config()
    run_id = "run-test"
    run_short = "ABC123"
    with connect(db) as conn:
        conn.execute("""
            INSERT INTO runs(run_id, run_short, profile_name, profile_snapshot, media_type, status, errors, warnings)
            VALUES(?, ?, 'default', ?, 'photos', 'created', '[]', '[]')
        """, (run_id, run_short, to_json_text(config)))
        conn.execute("""
            INSERT INTO items(item_id, run_id, raw_name, final_name, normalized_name, brand, category, quantity,
            visible_condition, confidence, confidence_reason, source, notes, sort_tier, sort_order)
            VALUES('item-1', ?, 'RAGU Projector', 'RAGU Projector', 'ragu projector', 'RAGU', 'Electronics', 1,
            'Used', 'Verified', 'Brand visible', 'User Visual', 'Similar model tested working, no remote', 2, 1)
        """, (run_id,))
        for idx, price in enumerate([32, 35, 30], start=1):
            conn.execute("""
                INSERT INTO evidence(evidence_id, item_id, source_type, source_name, url_platform, price, listing_type, refresh_status)
                VALUES(?, 'item-1', 'url', 'user_url', 'ebay', ?, 'sold', 'never')
            """, (f"ev-{idx}", price))
        compute_run_valuations(conn, run_id, config)
        exporter = WixCsvExporter(config, tmp_path / "exports")
        result = exporter.export(conn, run_id)
        assert result["validation_passed"] is True
        csv_path = Path(result["file_path"])
        rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
        assert rows[0]["handle"] == generate_handle(run_short, 1)
        assert rows[0]["SKU (auto)"] == generate_sku(run_short, 1)
        assert rows[0]["fieldType"] == "PRODUCT"
        assert rows[0]["Name"] == "RAGU Projector"
        assert rows[0]["Price"] != ""
