from fastapi import APIRouter, Query

from app.tools.process_run_tool import process_run_tool

router = APIRouter(prefix="/api/process", tags=["process"])


@router.post("/{run_id}")
async def process(run_id: str, provider: str | None = Query(default=None, description="openai or mock")):
    result = await process_run_tool(run_id, provider)
    return result.model_dump()
