import base64
import json
from unittest.mock import AsyncMock, MagicMock


def _make_upload_mcp(return_value: str) -> AsyncMock:
    mock = AsyncMock()
    mock.ainvoke.return_value = return_value
    return mock


async def test_upload_reads_file_and_encodes_base64(tmp_path):
    from deerflow.tools.adapters.ragflow.upload import _do_upload

    test_file = tmp_path / "report.pdf"
    test_file.write_bytes(b"fake pdf content")
    mock_mcp = _make_upload_mcp(json.dumps({"id": "doc-123", "name": "report.pdf", "progress": 0.0}))

    result = await _do_upload(
        path=str(test_file),
        dataset_id="ds-456",
        filename=None,
        metadata=None,
        upload_mcp=mock_mcp,
    )

    call_args = mock_mcp.ainvoke.call_args[0][0]
    assert call_args["dataset_id"] == "ds-456"
    assert call_args["filename"] == "report.pdf"
    assert base64.b64decode(call_args["file_content_base64"]) == b"fake pdf content"
    assert call_args["metadata"] is None
    assert json.loads(result)["id"] == "doc-123"


async def test_upload_uses_custom_filename(tmp_path):
    from deerflow.tools.adapters.ragflow.upload import _do_upload

    test_file = tmp_path / "report.pdf"
    test_file.write_bytes(b"data")
    mock_mcp = _make_upload_mcp(json.dumps({"id": "doc-999"}))

    await _do_upload(str(test_file), "ds-1", filename="custom_name.pdf", metadata=None, upload_mcp=mock_mcp)

    call_args = mock_mcp.ainvoke.call_args[0][0]
    assert call_args["filename"] == "custom_name.pdf"


async def test_upload_passes_metadata(tmp_path):
    from deerflow.tools.adapters.ragflow.upload import _do_upload

    test_file = tmp_path / "doc.txt"
    test_file.write_bytes(b"hello")
    mock_mcp = _make_upload_mcp(json.dumps({"id": "doc-1"}))
    meta = {"category": "finance", "year": 2024}

    await _do_upload(str(test_file), "ds-1", filename=None, metadata=meta, upload_mcp=mock_mcp)

    call_args = mock_mcp.ainvoke.call_args[0][0]
    assert call_args["metadata"] == meta


def test_make_upload_tool_returns_basetool():
    from langchain.tools import BaseTool

    from deerflow.tools.adapters.ragflow.upload import make_upload_tool

    mock_mcp = MagicMock()
    tool = make_upload_tool(mock_mcp)
    assert isinstance(tool, BaseTool)
    assert tool.name == "ragflow_upload"
    # runtime is LangGraph-injected — must NOT appear in the LLM-visible schema
    assert "runtime" not in tool.args


async def test_make_upload_tool_translates_virtual_path(tmp_path):
    """make_upload_tool wrapper must resolve /mnt/user-data/ virtual paths."""
    from types import SimpleNamespace

    from deerflow.tools.adapters.ragflow.upload import make_upload_tool

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    test_file = workspace / "doc.pdf"
    test_file.write_bytes(b"content")

    thread_data = {
        "workspace_path": str(workspace),
        "uploads_path": str(tmp_path / "uploads"),
        "outputs_path": str(tmp_path / "outputs"),
    }
    runtime = SimpleNamespace(state={"thread_data": thread_data}, context={})

    mock_mcp = AsyncMock()
    mock_mcp.ainvoke.return_value = '{"id": "doc-1"}'
    tool = make_upload_tool(mock_mcp)

    # Tool is called with virtual path; should resolve to actual workspace file
    result = await tool.coroutine(
        runtime=runtime,
        path="/mnt/user-data/workspace/doc.pdf",
        dataset_id="ds-1",
    )

    call_args = mock_mcp.ainvoke.call_args[0][0]
    # Actual host path was passed to MCP — not the virtual path
    assert "/mnt/user-data" not in call_args.get("file_content_base64", "")
    assert result  # masked output returned
