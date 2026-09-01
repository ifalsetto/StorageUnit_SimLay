from contextlib import contextmanager

import pytest
from fastapi import HTTPException

from app.core.database import connect, init_db, to_json_text
from app.routers import items
from app.schemas import ItemCreate, ItemDuplicateRequest, ItemUpdate


def use_temp_db(monkeypatch, db_path):
    @contextmanager
    def temp_db_session():
        conn = connect(db_path)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    monkeypatch.setattr(items, "db_session", temp_db_session)
    monkeypatch.setattr(items, "load_all_config", lambda: {"taxonomy": {}})


def seed_run(db_path, run_id="run-owner"):
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO runs(run_id, run_short, profile_name, profile_snapshot, owner, errors, warnings)
            VALUES(?, 'OWN001', 'default', ?, 'Unassigned', '[]', '[]')
            """,
            (run_id, to_json_text({"profile": "default"})),
        )
        conn.commit()


def test_schema_migration_adds_owner_and_soft_delete_columns(tmp_path):
    db_path = tmp_path / "simlay.db"
    with connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE runs(
                run_id TEXT PRIMARY KEY, run_short TEXT, created_at TEXT, profile_name TEXT, profile_snapshot TEXT,
                media_type TEXT, status TEXT, total_items INTEGER
            );
            CREATE TABLE items(item_id TEXT PRIMARY KEY, run_id TEXT, final_name TEXT, confidence TEXT);
            """
        )
        conn.commit()

    init_db(db_path)
    with connect(db_path) as conn:
        run_cols = {row["name"] for row in conn.execute("PRAGMA table_info(runs)")}
        item_cols = {row["name"] for row in conn.execute("PRAGMA table_info(items)")}

    assert "owner" in run_cols
    assert {"owner", "item_action", "manual_value_low", "manual_value_expected", "manual_value_high", "asking_price", "deleted_at"}.issubset(item_cols)


def test_owner_crud_soft_delete_restore_and_duplicate(tmp_path, monkeypatch):
    db_path = tmp_path / "simlay.db"
    init_db(db_path)
    seed_run(db_path)
    use_temp_db(monkeypatch, db_path)

    created = items.create_item(ItemCreate(
        run_id="run-owner", final_name="Thomas Item", confidence="Verified", source="Photo",
        owner="Thomas", item_action="Sell", manual_value_low=20, manual_value_expected=30,
        manual_value_high=40, asking_price=45,
    ))
    item_id = created["item_id"]

    thomas = items.list_items("run-owner", owner="Thomas", include_deleted=False)
    assert [row["item_id"] for row in thomas["items"]] == [item_id]
    assert thomas["items"][0]["display_value_expected"] == 30

    items.update_item(item_id, ItemUpdate(owner="Mine", asking_price=50))
    assert items.list_items("run-owner", owner="Thomas", include_deleted=False)["items"] == []
    assert items.list_items("run-owner", owner="Mine", include_deleted=False)["items"][0]["asking_price"] == 50

    with pytest.raises(HTTPException) as exc:
        items.delete_item(item_id, confirm=False)
    assert exc.value.status_code == 400

    deleted = items.delete_item(item_id, confirm=True, reason="owner dashboard cleanup")
    assert deleted["recoverable"] is True
    assert items.list_items("run-owner", owner="Mine", include_deleted=False)["items"] == []
    trash = items.list_items("run-owner", owner="Mine", include_deleted=True)["items"]
    assert trash[0]["deleted_at"] is not None

    items.restore_item(item_id)
    duplicated = items.duplicate_item(item_id, ItemDuplicateRequest(owner="Mine"))
    assert duplicated["item_id"] != item_id
    mine_items = items.list_items("run-owner", owner="Mine", include_deleted=False)["items"]
    assert len(mine_items) == 2
    copy = next(row for row in mine_items if row["item_id"] == duplicated["item_id"])
    assert copy["flag_duplicate_suspect"] == 1


def test_owner_summary_is_separated(tmp_path, monkeypatch):
    db_path = tmp_path / "simlay.db"
    init_db(db_path)
    seed_run(db_path)
    use_temp_db(monkeypatch, db_path)

    for owner, value in (("Thomas", 25), ("Mine", 75), ("Unassigned", 10)):
        items.create_item(ItemCreate(
            run_id="run-owner", final_name=f"{owner} item", confidence="Inferred",
            owner=owner, item_action="Hold", manual_value_expected=value,
        ))

    summary = items.inventory_summary("run-owner")
    assert summary["owners"]["Thomas"]["value_expected"] == 25
    assert summary["owners"]["Mine"]["value_expected"] == 75
    assert summary["owners"]["Unassigned"]["value_expected"] == 10
