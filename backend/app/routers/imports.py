from __future__ import annotations

import json

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.core.config import load_all_config
from app.core.database import db_session, rows_to_dicts
from app.models.enums import InventoryOwner
from app.services.inventory_import import IMPORT_SOURCE_NAME, import_photo_inventory, relink_imported_media

router = APIRouter(prefix="/api/imports", tags=["imports"])


def _ensure_import_schema(conn) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS inventory_import_refs (
            import_ref_id TEXT PRIMARY KEY,
            import_batch_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            source_name TEXT NOT NULL,
            external_ref TEXT NOT NULL,
            source_photo_name TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(run_id, source_name, external_ref),
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
            FOREIGN KEY (item_id) REFERENCES items(item_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_inventory_import_refs_run ON inventory_import_refs(run_id, source_name);
        CREATE INDEX IF NOT EXISTS idx_inventory_import_refs_item ON inventory_import_refs(item_id);
        """
    )


@router.post("/photo-inventory/{run_id}")
async def import_photo_inventory_file(
    run_id: str,
    file: UploadFile = File(...),
    owner: InventoryOwner = Query(default=InventoryOwner.UNASSIGNED),
    dry_run: bool = Query(default=True),
    source_name: str = Query(default=IMPORT_SOURCE_NAME, min_length=1, max_length=100),
):
    """Import a private SimLay photo-inventory JSON file into one existing run.

    Safety defaults:
    - dry_run defaults to true.
    - owner defaults to Unassigned; ownership is never inferred from the file.
    - existing source item IDs are idempotency keys, so re-imports do not duplicate them.
    - source URLs are preserved only as reference-only evidence and are excluded from valuation.
    - photo names are recorded for a later exact-basename relink after the private photos are uploaded locally.
    """
    filename = (file.filename or "").lower()
    if filename and not filename.endswith(".json"):
        raise HTTPException(400, "Photo inventory import requires a .json file")
    try:
        raw = await file.read()
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(400, f"Invalid JSON inventory file: {exc}") from exc

    config = load_all_config()
    with db_session() as conn:
        _ensure_import_schema(conn)
        try:
            return import_photo_inventory(
                conn,
                run_id,
                payload,
                config,
                owner=owner,
                source_name=source_name,
                dry_run=dry_run,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc


@router.post("/photo-inventory/{run_id}/relink-media")
def relink_photo_inventory_media(
    run_id: str,
    source_name: str = Query(default=IMPORT_SOURCE_NAME, min_length=1, max_length=100),
):
    """Relink imported item photo references to media already uploaded into the same run.

    Matching is exact by filename basename. Zero matches stay missing. Multiple matches are reported as ambiguous.
    SimLay never guesses between ambiguous photos and never overwrites an existing representative image.
    """
    with db_session() as conn:
        _ensure_import_schema(conn)
        try:
            return relink_imported_media(conn, run_id, source_name=source_name)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc


@router.get("/photo-inventory/{run_id}/status")
def photo_inventory_import_status(
    run_id: str,
    source_name: str = Query(default=IMPORT_SOURCE_NAME, min_length=1, max_length=100),
):
    with db_session() as conn:
        _ensure_import_schema(conn)
        run = conn.execute("SELECT run_id FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if not run:
            raise HTTPException(404, "Run not found")
        rows = rows_to_dicts(
            conn.execute(
                """
                SELECT r.import_batch_id, r.external_ref, r.source_photo_name, r.created_at,
                       i.item_id, i.final_name, i.owner, i.confidence, i.source,
                       i.representative_image_id, i.deleted_at
                FROM inventory_import_refs r
                JOIN items i ON i.item_id=r.item_id
                WHERE r.run_id=? AND r.source_name=?
                ORDER BY r.created_at, r.external_ref
                """,
                (run_id, source_name),
            ).fetchall()
        )
    return {
        "run_id": run_id,
        "source_name": source_name,
        "count": len(rows),
        "linked_photo_count": sum(1 for row in rows if row.get("representative_image_id")),
        "deleted_count": sum(1 for row in rows if row.get("deleted_at")),
        "items": rows,
    }
