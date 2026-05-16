from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import load_all_config, resolve_storage_path
from app.core.database import db_session, row_to_dict
from app.services.csv_exporter import WixCsvExporter
from app.services.audit_exporter import export_audit_json
from app.services.valuation import compute_run_valuations

router = APIRouter(prefix="/api/exports", tags=["exports"])

@router.post("/csv/{run_id}")
def export_csv(run_id: str):
    config = load_all_config()
    exports_dir = resolve_storage_path(config, "exports_dir")
    with db_session() as conn:
        compute_run_valuations(conn, run_id, config)
        exporter = WixCsvExporter(config, exports_dir)
        try:
            return exporter.export(conn, run_id)
        except Exception as exc:
            raise HTTPException(400, str(exc))

@router.post("/audit/{run_id}")
def export_audit(run_id: str):
    config = load_all_config()
    exports_dir = resolve_storage_path(config, "exports_dir")
    with db_session() as conn:
        try:
            return export_audit_json(conn, run_id, config, exports_dir)
        except Exception as exc:
            raise HTTPException(400, str(exc))

@router.get("/download/{export_id}")
def download_export(export_id: str):
    with db_session() as conn:
        export = row_to_dict(conn.execute("SELECT * FROM exports WHERE export_id=?", (export_id,)).fetchone())
        if not export:
            raise HTTPException(404, "Export not found")
        path = Path(export["file_path"])
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[2] / path
        if not path.exists():
            raise HTTPException(404, "Export file missing")
        return FileResponse(str(path), filename=path.name)
