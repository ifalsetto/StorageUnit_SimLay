from fastapi import APIRouter, HTTPException, Query
from app.core.config import load_all_config
from app.core.database import db_session
from app.services.pipeline import process_run

router = APIRouter(prefix="/api/process", tags=["process"])

@router.post("/{run_id}")
async def process(run_id: str, provider: str | None = Query(default=None, description="openai or mock")):
    config = load_all_config()
    with db_session() as conn:
        try:
            return await process_run(conn, run_id, config, provider_name=provider)
        except Exception as exc:
            raise HTTPException(400, str(exc))
