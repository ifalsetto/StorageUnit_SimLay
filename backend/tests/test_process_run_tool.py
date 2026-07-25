import asyncio
import importlib

from app.core.database import db_session, init_db
from app.tools.base import ToolResult

process_run_tool_module = importlib.import_module("app.tools.process_run_tool")


def run_tool(run_id, provider=None) -> ToolResult:
    return asyncio.run(process_run_tool_module.process_run_tool(run_id, provider))


def configure_temp_db(monkeypatch, tmp_path):
    db_path = tmp_path / "process_run_tool.db"
    init_db(db_path)
    monkeypatch.setattr(
        process_run_tool_module,
        "db_session",
        lambda: db_session(db_path),
    )
    return db_path


def insert_run(db_path, run_id="run_tool_test"):
    with db_session(db_path) as conn:
        conn.execute(
            """
            INSERT INTO runs(run_id, run_short, profile_name, profile_snapshot)
            VALUES(?, ?, 'default', '{}')
            """,
            (run_id, f"short_{run_id}"),
        )


def assert_tool_result_shape(result: ToolResult):
    dumped = result.model_dump()
    assert set(dumped) == {
        "success",
        "data",
        "error_code",
        "message",
        "retryable",
        "next_action",
    }


def test_missing_run_id_returns_structured_error():
    result = run_tool("")

    assert result.success is False
    assert result.error_code == "MISSING_RUN_ID"
    assert result.retryable is False
    assert result.next_action
    assert_tool_result_shape(result)


def test_run_not_found_returns_structured_error(monkeypatch, tmp_path):
    configure_temp_db(monkeypatch, tmp_path)

    result = run_tool("run_missing")

    assert result.success is False
    assert result.error_code == "RUN_NOT_FOUND"
    assert result.retryable is False
    assert result.data is None
    assert_tool_result_shape(result)


def test_no_media_uploaded_returns_structured_error(monkeypatch, tmp_path):
    db_path = configure_temp_db(monkeypatch, tmp_path)
    insert_run(db_path)

    result = run_tool("run_tool_test")

    assert result.success is False
    assert result.error_code == "NO_MEDIA_UPLOADED"
    assert result.retryable is False
    assert result.data is None
    assert_tool_result_shape(result)


def test_successful_processing_with_mock_provider(monkeypatch, tmp_path):
    db_path = configure_temp_db(monkeypatch, tmp_path)
    insert_run(db_path)

    with db_session(db_path) as conn:
        conn.execute(
            """
            INSERT INTO media_inputs(media_id, run_id, file_path, file_type, sequence_order)
            VALUES(?, ?, ?, ?, ?)
            """,
            (
                "media_tool_test",
                "run_tool_test",
                str(tmp_path / "mock_tool_chest.jpg"),
                "image/jpeg",
                1,
            ),
        )

    result = run_tool("run_tool_test", provider="mock")

    assert result.success is True
    assert result.error_code is None
    assert result.retryable is False
    assert result.data["status"] == "processed"
    assert result.data["items_created"] == 1
    assert_tool_result_shape(result)
