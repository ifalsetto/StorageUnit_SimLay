from typing import Any

from app.core.config import load_all_config
from app.core.database import db_session
from app.services.pipeline import process_run
from app.tools.base import ToolResult, tool_error, tool_success


async def process_run_tool(run_id: str | None, provider: str | None = None) -> ToolResult:
    """Run the existing processing pipeline behind a stable agent-facing contract."""
    if not isinstance(run_id, str) or not run_id.strip():
        return tool_error(
            "MISSING_RUN_ID",
            "run_id is required.",
            retryable=False,
            next_action="Provide a valid run_id and retry.",
        )

    try:
        config = load_all_config()
        with db_session() as conn:
            run = conn.execute(
                "SELECT run_id FROM runs WHERE run_id=?",
                (run_id,),
            ).fetchone()
            if not run:
                return tool_error(
                    "RUN_NOT_FOUND",
                    f"Run not found: {run_id}",
                    retryable=False,
                    next_action="Create or select an existing run_id before processing.",
                )

            media = conn.execute(
                "SELECT media_id FROM media_inputs WHERE run_id=? LIMIT 1",
                (run_id,),
            ).fetchone()
            if not media:
                return tool_error(
                    "NO_MEDIA_UPLOADED",
                    "No media uploaded for run.",
                    retryable=False,
                    next_action="Upload at least one media file for the run, then retry processing.",
                )

            result: dict[str, Any] = await process_run(
                conn,
                run_id,
                config,
                provider_name=provider,
            )

            if result.get("status") == "failed":
                return tool_error(
                    "PROCESSING_FAILED",
                    "Run processing failed to produce processed items.",
                    retryable=True,
                    next_action="Review the provider/media warnings and retry processing.",
                    data=result,
                )

            return tool_success(
                result,
                message="Run processed successfully.",
            )
    except ValueError as exc:
        return tool_error(
            "VALIDATION_ERROR",
            str(exc),
            retryable=False,
            next_action="Correct the request or run data, then retry.",
        )
    except Exception as exc:
        return tool_error(
            "UNEXPECTED_PROCESSING_ERROR",
            str(exc) or "Unexpected processing error.",
            retryable=True,
            next_action="Retry processing. If the error persists, inspect backend logs.",
        )
