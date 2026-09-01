from contextlib import contextmanager
from pathlib import Path

from app.core.database import connect, init_db, to_json_text
from app.routers import runs


def seed_large_run_history(db_path: Path, count: int = 500) -> None:
    with connect(db_path) as conn:
        for idx in range(count):
            run_id = f"run-{idx:04d}"
            created_at = f"2026-05-{(idx % 28) + 1:02d}T{idx // 28:02d}:00:00"
            conn.execute(
                """
                INSERT INTO runs(
                    run_id, run_short, created_at, profile_name, profile_snapshot,
                    media_type, status, owner, total_items, errors, warnings
                )
                VALUES(?, ?, ?, 'default', ?, 'photos', 'created', 'Unassigned', ?, '[]', '[]')
                """,
                (run_id, f"R{idx:04d}", created_at, to_json_text({"profile": "default"}), idx),
            )
            conn.execute(
                """
                INSERT INTO items(item_id, run_id, final_name, confidence)
                VALUES(?, ?, ?, 'Verified')
                """,
                (f"item-{idx:04d}", run_id, f"Item {idx}"),
            )
            conn.execute(
                """
                INSERT INTO media_inputs(media_id, run_id, file_path, file_type)
                VALUES(?, ?, ?, 'image')
                """,
                (f"media-{idx:04d}", run_id, f"uploads/{idx}.jpg"),
            )
        conn.commit()


def use_temp_runs_db(monkeypatch, db_path: Path) -> None:
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

    monkeypatch.setattr(runs, "db_session", temp_db_session)


def test_list_runs_returns_ordered_metadata_without_detail_loads(tmp_path, monkeypatch):
    db_path = tmp_path / "simlay.db"
    init_db(db_path)
    seed_large_run_history(db_path)
    use_temp_runs_db(monkeypatch, db_path)

    payload = runs.list_runs()

    assert len(payload["runs"]) == 500
    assert payload["runs"] == sorted(payload["runs"], key=lambda row: row["created_at"], reverse=True)
    assert set(payload["runs"][0]) == {
        "run_id",
        "run_short",
        "created_at",
        "profile_name",
        "media_type",
        "status",
        "owner",
        "total_items",
    }
    assert "items" not in payload["runs"][0]
    assert "media" not in payload["runs"][0]
    assert "evidence" not in payload["runs"][0]


def test_runs_history_query_uses_history_index(tmp_path):
    db_path = tmp_path / "simlay.db"
    init_db(db_path)

    with connect(db_path) as conn:
        index = conn.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'index' AND name = 'idx_runs_history_list'
            """
        ).fetchone()
        plan_rows = conn.execute(
            """
            EXPLAIN QUERY PLAN
            SELECT run_id, run_short, created_at, profile_name, media_type, status, owner, total_items
            FROM runs
            ORDER BY created_at DESC
            """
        ).fetchall()

    assert index is not None
    assert "created_at DESC" in index["sql"]
    plan = " ".join(row["detail"] for row in plan_rows)
    assert "idx_runs_history_list" in plan
