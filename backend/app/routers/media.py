import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException

from app.core.config import load_all_config, resolve_storage_path
from app.core.database import db_session, rows_to_dicts
from app.core.ids import new_uuid
from app.services.video import extract_keyframes

router = APIRouter(prefix="/api/media", tags=["media"])

@router.post("/upload/{run_id}")
def upload_media(run_id: str, files: list[UploadFile] = File(...)):
    config = load_all_config()
    upload_root = resolve_storage_path(config, "uploads_dir") / run_id
    upload_root.mkdir(parents=True, exist_ok=True)
    created = []
    with db_session() as conn:
        run = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if not run:
            raise HTTPException(404, "Run not found")
        seq = conn.execute("SELECT COUNT(*) c FROM media_inputs WHERE run_id=?", (run_id,)).fetchone()["c"]
        for f in files:
            seq += 1
            safe_name = Path(f.filename or f"upload_{seq}").name
            file_path = upload_root / safe_name
            with file_path.open("wb") as out:
                shutil.copyfileobj(f.file, out)
            suffix = file_path.suffix.lower()
            if suffix in {".mp4", ".mov", ".mkv", ".avi"}:
                key_dir = upload_root / f"keyframes_{seq}"
                frames = extract_keyframes(file_path, key_dir, max_keyframes=int(config["app_config"]["vision"]["video"].get("max_keyframes", 100)))
                for kidx, frame in enumerate(frames, start=1):
                    media_id = new_uuid("media")
                    rel = frame.relative_to(Path(__file__).resolve().parents[2])
                    conn.execute("INSERT INTO media_inputs(media_id, run_id, file_path, file_type, sequence_order, timestamp_in_video) VALUES(?, ?, ?, 'keyframe', ?, ?)", (media_id, run_id, str(rel), seq + kidx - 1, None))
                    created.append({"media_id": media_id, "file_path": str(rel), "file_type": "keyframe"})
            else:
                media_id = new_uuid("media")
                rel = file_path.relative_to(Path(__file__).resolve().parents[2])
                conn.execute("INSERT INTO media_inputs(media_id, run_id, file_path, file_type, sequence_order) VALUES(?, ?, ?, 'photo', ?)", (media_id, run_id, str(rel), seq))
                created.append({"media_id": media_id, "file_path": str(rel), "file_type": "photo"})
        conn.execute("UPDATE runs SET media_count=(SELECT COUNT(*) FROM media_inputs WHERE run_id=?) WHERE run_id=?", (run_id, run_id))
    return {"uploaded": created}

@router.get("/{run_id}")
def list_media(run_id: str):
    with db_session() as conn:
        rows = rows_to_dicts(conn.execute("SELECT * FROM media_inputs WHERE run_id=? ORDER BY sequence_order", (run_id,)).fetchall())
    return {"media": rows}
