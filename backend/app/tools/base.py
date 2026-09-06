from typing import Any

from pydantic import BaseModel


class ToolResult(BaseModel):
    success: bool
    data: Any | None = None
    error_code: str | None = None
    message: str
    retryable: bool = False
    next_action: str | None = None


def tool_success(
    data: Any = None,
    *,
    message: str = "Operation completed successfully.",
    next_action: str | None = None,
) -> ToolResult:
    return ToolResult(
        success=True,
        data=data,
        error_code=None,
        message=message,
        retryable=False,
        next_action=next_action,
    )


def tool_error(
    error_code: str,
    message: str,
    *,
    retryable: bool = False,
    next_action: str | None = None,
    data: Any = None,
) -> ToolResult:
    return ToolResult(
        success=False,
        data=data,
        error_code=error_code,
        message=message,
        retryable=retryable,
        next_action=next_action,
    )
