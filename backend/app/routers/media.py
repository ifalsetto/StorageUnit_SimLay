import shutil
from pathlib import Path
from typing import List

from fastapi import APIRouter, UploadFile, File, HTTPException

from app.core.config import load_all_config, resolve_storage_path
from app.core.database import db_session, rows_to_dicts
from app.core.ids import new_uuid
from app.services.video import extract_keyframes

router = APIRouter(prefix="/api/media", tags=["media"])

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _verify_run_exists(conn, run_id: str) -> None:
    run = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")


def _next_sequence(conn, run_id: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) c FROM media_inputs WHERE run_id=?",
        (run_id,),
    ).fetchone()
    return int(row["c"] or 0)


def _safe_filename(filename: str | None, fallback: str) -> str:
    name = Path(filename or fallback).name
    if not name or name in {".", ".."}:
        return fallback
    return name


def _save_upload_file(upload_file: UploadFile, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as out:
        shutil.copyfileobj(upload_file.file, out)


def _register_uploaded_file(conn, config, run_id: str, upload_file: UploadFile, seq: int, upload_root: Path):
    safe_name = _safe_filename(upload_file.filename, f"upload_{seq}")
    file_path = upload_root / safe_name

    _save_upload_file(upload_file, file_path)

    suffix = file_path.suffix.lower()
    created = []

    if suffix in {".mp4", ".mov", ".mkv", ".avi", ".m4v"}:
        key_dir = upload_root / f"keyframes_{seq}"
        max_keyframes = int(
            config["app_config"]["vision"]["video"].get("max_keyframes", 100)
        )

        frames = extract_keyframes(
            file_path,
            key_dir,
            max_keyframes=max_keyframes,
        )

        for kidx, frame in enumerate(frames, start=1):
            media_id = new_uuid("media")
            rel = frame.relative_to(BACKEND_DIR)

            conn.execute(
                """
                INSERT INTO media_inputs(
                    media_id,
                    run_id,
                    file_path,
                    file_type,
                    sequence_order,
                    timestamp_in_video
                )
                VALUES(?, ?, ?, 'keyframe', ?, ?)
                """,
                (
                    media_id,
                    run_id,
                    str(rel),
                    seq + kidx - 1,
                    None,
                ),
            )

            created.append(
                {
                    "media_id": media_id,
                    "run_id": run_id,
                    "file_path": str(rel),
                    "file_type": "keyframe",
                    "sequence_order": seq + kidx - 1,
                }
            )

    else:
        media_id = new_uuid("media")
        rel = file_path.relative_to(BACKEND_DIR)

        conn.execute(
            """
            INSERT INTO media_inputs(
                media_id,
                run_id,
                file_path,
                file_type,
                sequence_order
            )
            VALUES(?, ?, ?, 'photo', ?)
            """,
            (
                media_id,
                run_id,
                str(rel),
                seq,
            ),
        )

        created.append(
            {
                "media_id": media_id,
                "run_id": run_id,
                "file_path": str(rel),
                "file_type": "photo",
                "sequence_order": seq,
            }
        )

    return created


@router.post("/upload-one/{run_id}")
def upload_one_media(run_id: str, file: UploadFile = File(...)):
    """
    Simple single-file upload endpoint.

    Use this endpoint for Swagger testing and frontend upload.
    Swagger should show a normal Choose File button here.
    """
    config = load_all_config()
    upload_root = resolve_storage_path(config, "uploads_dir") / run_id
    upload_root.mkdir(parents=True, exist_ok=True)

    with db_session() as conn:
        _verify_run_exists(conn, run_id)

        seq = _next_sequence(conn, run_id) + 1
        created = _register_uploaded_file(
            conn=conn,
            config=config,
            run_id=run_id,
            upload_file=file,
            seq=seq,
            upload_root=upload_root,
        )

        conn.execute(
            """
            UPDATE runs
            SET media_count=(
                SELECT COUNT(*)
                FROM media_inputs
                WHERE run_id=?
            )
            WHERE run_id=?
            """,
            (run_id, run_id),
        )

    return {"uploaded": created}


@router.post("/upload/{run_id}")
def upload_media(run_id: str, files: List[UploadFile] = File(...)):
    """
    Multi-file upload endpoint.

    Some Swagger versions display this badly as array<string>.
    If Swagger does that, use /upload-one/{run_id} instead.
    """
    config = load_all_config()
    upload_root = resolve_storage_path(config, "uploads_dir") / run_id
    upload_root.mkdir(parents=True, exist_ok=True)

    created = []

    with db_session() as conn:
        _verify_run_exists(conn, run_id)

        seq = _next_sequence(conn, run_id)

        for upload_file in files:
            seq += 1
            created.extend(
                _register_uploaded_file(
                    conn=conn,
                    config=config,
                    run_id=run_id,
                    upload_file=upload_file,
                    seq=seq,
                    upload_root=upload_root,
                )
            )

        conn.execute(
            """
            UPDATE runs
            SET media_count=(
                SELECT COUNT(*)
                FROM media_inputs
                WHERE run_id=?
            )
            WHERE run_id=?
            """,
            (run_id, run_id),
        )

    return {"uploaded": created}


@router.get("/{run_id}")
def list_media(run_id: str):
    with db_session() as conn:
        rows = rows_to_dicts(
            conn.execute(
                """
                SELECT *
                FROM media_inputs
                WHERE run_id=?
                ORDER BY sequence_order
                """,
                (run_id,),
            ).fetchall()
        )

    return {"media": rows}