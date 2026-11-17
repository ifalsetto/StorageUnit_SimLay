# AI Agent Tool Contracts

This backend exposes small agent-facing wrappers around existing application services. The wrappers do not replace service logic; they provide stable inputs, outputs, and structured failure handling for callers such as AI agents and automation.

## `ToolResult`

All backend tools return `app.tools.base.ToolResult`.

```json
{
  "success": true,
  "data": {},
  "error_code": null,
  "message": "Run processed successfully.",
  "retryable": false,
  "next_action": null
}
```

| Field | Type | Meaning |
| --- | --- | --- |
| `success` | boolean | `true` when the tool completed successfully. |
| `data` | any or null | Tool-specific output or structured failure context. |
| `error_code` | string or null | Stable machine-readable error code. `null` on success. |
| `message` | string | Human-readable result summary. |
| `retryable` | boolean | Whether retrying the same operation may succeed without first correcting caller input/state. |
| `next_action` | string or null | Suggested corrective or follow-up action. |

Use `tool_success()` and `tool_error()` to construct results instead of creating ad hoc response dictionaries.

## `process_run_tool`

Module: `app.tools.process_run_tool`

### Input

```python
await process_run_tool(run_id: str | None, provider: str | None = None)
```

- `run_id` is required and must be a non-empty string identifying an existing run.
- `provider` is optional and is passed through to the existing processing pipeline. Current application providers include `openai` and `mock`.

### Behavior

The tool:

1. Validates `run_id`.
2. Loads application configuration with `load_all_config()`.
3. Opens a database transaction with `db_session()`.
4. Confirms the run exists and has uploaded media.
5. Calls the existing `app.services.pipeline.process_run()` service.
6. Returns a `ToolResult` for both success and failure paths.

The tool does not duplicate or replace pipeline processing logic.

### Success output

`data` contains the existing pipeline result, for example:

```json
{
  "success": true,
  "data": {
    "status": "processed",
    "items_created": 1,
    "warnings": []
  },
  "error_code": null,
  "message": "Run processed successfully.",
  "retryable": false,
  "next_action": null
}
```

## Error codes and retry behavior

| Error code | Meaning | Retryable | Expected next action |
| --- | --- | --- | --- |
| `MISSING_RUN_ID` | `run_id` is absent, non-string, or blank. | No | Supply a valid run ID. |
| `RUN_NOT_FOUND` | No run exists for the supplied ID. | No | Create or select an existing run. |
| `NO_MEDIA_UPLOADED` | The run exists but has no media inputs. | No | Upload media, then call the tool again. |
| `PROCESSING_FAILED` | The pipeline ran but returned a failed processing result, such as no detected items. | Yes | Review provider/media warnings and retry when appropriate. |
| `VALIDATION_ERROR` | Existing service validation rejected the request or provider. | No | Correct the request or run data before retrying. |
| `UNEXPECTED_PROCESSING_ERROR` | An unclassified configuration, database, or processing exception occurred. | Yes | Retry once; if it persists, inspect backend logs. |

`retryable=false` means the caller should change input or application state before invoking the tool again. `retryable=true` means a retry may be useful, but callers should still use bounded retry policies rather than retrying indefinitely.

## HTTP process route

`POST /api/process/{run_id}` delegates to `process_run_tool(run_id, provider)` and returns `result.model_dump()`. Errors are therefore returned with the same structured `ToolResult` schema instead of raw `HTTPException` string bodies.
