import sqlite3

from app.core.database import SCHEMA
from app.routers.imports import _ensure_import_schema
from app.services.inventory_import import import_photo_inventory, relink_imported_media


def make_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _ensure_import_schema(conn)
    conn.execute(
        """
        INSERT INTO runs(run_id, run_short, profile_name, profile_snapshot, status, errors, warnings)
        VALUES('run_1', 'R001', 'default', '{}', 'created', '[]', '[]')
        """
    )
    return conn


def config():
    return {"taxonomy": {}}


def sample_payload():
    return {
        "items": [
            {
                "item_id": "I-0041",
                "title": "1987 Topps Bo Jackson Future Stars #170 rookie card",
                "photo": "bo.jpg",
                "value_low": 2.47,
                "value_high": 3.85,
                "list_price": 4.99,
                "condition": "Raw / ungraded; exact grade not established",
                "confidence": "Verified",
                "source": "Photo + Web (Cited)",
                "notes": "Working range is for an ungraded copy.",
                "source_url": "https://example.com/bo-comp",
            }
        ]
    }


def test_import_defaults_to_unassigned_and_is_idempotent():
    conn = make_conn()

    first = import_photo_inventory(conn, "run_1", sample_payload(), config())
    second = import_photo_inventory(conn, "run_1", sample_payload(), config())

    assert first["created_count"] == 1
    assert first["owner"] == "Unassigned"
    assert second["created_count"] == 0
    assert second["already_imported"] == 1

    item = conn.execute("SELECT * FROM items").fetchone()
    assert item["owner"] == "Unassigned"
    assert item["confidence"] == "Verified"
    assert item["source"] == "Web (Cited)"
    assert item["manual_value_low"] == 2.47
    assert item["manual_value_expected"] is None
    assert item["manual_value_high"] == 3.85
    assert item["asking_price"] == 4.99
    assert item["visible_condition"] == "Unknown"
    assert "Imported original condition text" in item["notes"]

    evidence = conn.execute("SELECT * FROM evidence").fetchone()
    assert evidence["url"] == "https://example.com/bo-comp"
    assert evidence["included_in_valuation"] == 0
    assert evidence["exclusion_reason"] == "reference_only"
    assert evidence["price"] is None


def test_import_assigns_thomas_only_when_explicitly_requested():
    conn = make_conn()

    result = import_photo_inventory(conn, "run_1", sample_payload(), config(), owner="Thomas")

    assert result["owner"] == "Thomas"
    item = conn.execute("SELECT owner FROM items").fetchone()
    assert item["owner"] == "Thomas"


def test_dry_run_does_not_write_items_or_import_refs():
    conn = make_conn()

    result = import_photo_inventory(conn, "run_1", sample_payload(), config(), owner="Thomas", dry_run=True)

    assert result["dry_run"] is True
    assert result["would_create"] == 1
    assert conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM inventory_import_refs").fetchone()[0] == 0


def test_relink_uses_exact_basename_and_does_not_guess_ambiguous_matches():
    conn = make_conn()
    import_photo_inventory(conn, "run_1", sample_payload(), config(), owner="Thomas")
    item_id = conn.execute("SELECT item_id FROM items").fetchone()[0]

    conn.execute(
        """
        INSERT INTO media_inputs(media_id, run_id, file_path, file_type, sequence_order)
        VALUES('media_1', 'run_1', 'data/uploads/run_1/bo.jpg', 'photo', 1)
        """
    )
    result = relink_imported_media(conn, "run_1")
    assert result["linked"] == 1
    item = conn.execute("SELECT representative_image_id FROM items WHERE item_id=?", (item_id,)).fetchone()
    assert item["representative_image_id"] == "media_1"

    # Reset the item and add a second same-basename candidate. SimLay must refuse to choose.
    conn.execute("UPDATE items SET representative_image_id=NULL, detected_in_media='[]' WHERE item_id=?", (item_id,))
    conn.execute(
        """
        INSERT INTO media_inputs(media_id, run_id, file_path, file_type, sequence_order)
        VALUES('media_2', 'run_1', 'data/uploads/run_1/other/bo.jpg', 'photo', 2)
        """
    )
    ambiguous = relink_imported_media(conn, "run_1")
    assert ambiguous["linked"] == 0
    assert ambiguous["ambiguous_count"] == 1
    item = conn.execute("SELECT representative_image_id FROM items WHERE item_id=?", (item_id,)).fetchone()
    assert item["representative_image_id"] is None
