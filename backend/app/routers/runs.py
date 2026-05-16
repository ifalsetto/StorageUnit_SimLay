import json
import uuid
from fastapi import APIRouter, HTTPException

from app.core.config import load_all_config
from app.core.database import db_session, row_to_dict, rows_to_dicts, to_json_text, from_json_text
from app.core.ids import make_run_short
from app.schemas import CreateRunRequest

router = APIRouter(prefix="/api/runs", tags=["runs"])

@router.post("")
def create_run(payload: CreateRunRequest):
    config = load_all_config(payload.profile_name)
    run_id = str(uuid.uuid4())
    run_short = make_run_short(f"{payload.profile_name}:{run_id}")
    with db_session() as conn:
        conn.execute("""
            INSERT INTO runs(run_id, run_short, profile_name, profile_snapshot, media_type, status, errors, warnings)
            VALUES(?, ?, ?, ?, ?, 'created', ?, ?)
        """, (run_id, run_short, payload.profile_name, to_json_text(config), payload.media_type, to_json_text([]), to_json_text([])))
    return {"run_id": run_id, "run_short": run_short, "profile_name": payload.profile_name, "status": "created"}

@router.get("")
def list_runs():
    with db_session() as conn:
        rows = rows_to_dicts(conn.execute("SELECT run_id, run_short, created_at, profile_name, media_type, status, total_items FROM runs ORDER BY created_at DESC").fetchall())
    return {"runs": rows}

@router.get("/{run_id}")
def get_run(run_id: str):
    with db_session() as conn:
        run = row_to_dict(conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone())
        if not run:
            raise HTTPException(404, "Run not found")
        run["errors"] = from_json_text(run.get("errors"), [])
        run["warnings"] = from_json_text(run.get("warnings"), [])
    return run
