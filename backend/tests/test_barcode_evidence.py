"""Barcode observations are inventory evidence, never sale-price evidence."""
from app.core.database import connect, init_db
from app.routers.evidence import _insert_evidence


def test_unpriced_barcode_is_persisted_but_excluded_from_valuation(tmp_path):
    database_path = tmp_path / "barcode-evidence.db"
    init_db(database_path)
    with connect(database_path) as conn:
        conn.execute(
            "INSERT INTO runs(run_id, run_short, profile_name, profile_snapshot, owner) VALUES(?, ?, ?, ?, ?)",
            ("run_1", "TEST01", "default", "{}", "Mine"),
        )
        conn.execute(
            "INSERT INTO items(item_id, run_id, final_name, confidence, owner) VALUES(?, ?, ?, ?, ?)",
            ("item_1", "run_1", "Test scanner item", "Unknown", "Mine"),
        )
        _insert_evidence(
            conn,
            evidence_id="ev_barcode_1",
            item_id="item_1",
            source_type="barcode",
            source_name="local_barcode_scan",
            url_title="Barcode ean_13: 1234567890123",
            listing_type="observation",
            price=None,
            notes="Unverified local barcode observation",
        )
        row = conn.execute(
            "SELECT source_type, listing_type, price, included_in_valuation, exclusion_reason, url_title "
            "FROM evidence WHERE evidence_id='ev_barcode_1'"
        ).fetchone()
        assert row["source_type"] == "barcode"
        assert row["listing_type"] == "observation"
        assert row["price"] is None
        assert row["included_in_valuation"] == 0
        assert row["exclusion_reason"] == "price_null"
        assert "1234567890123" in row["url_title"]
