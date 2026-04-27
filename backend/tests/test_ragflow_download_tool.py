import base64
import json
from pathlib import Path
from unittest.mock import MagicMock


def _make_download_mcp(content_bytes: bytes) -> MagicMock:
    mock = MagicMock()
    mock.invoke.return_value = json.dumps({"content_base64": base64.b64encode(content_bytes).decode()})
    return mock


def test_download_saves_file_to_output_dir(tmp_path):
    from deerflow.tools.adapters.ragflow.download import _do_download

    content = b"fake file content"
    mock_mcp = _make_download_mcp(content)
    output_dir = tmp_path / "downloads"

    result_str = _do_download(
        doc_ids=["doc-123"],
        output_dir=str(output_dir),
        filenames=["report.pdf"],
        download_mcp=mock_mcp,
    )

    saved_paths = json.loads(result_str)
    assert len(saved_paths) == 1
    saved = Path(saved_paths[0])
    assert saved.exists()
    assert saved.read_bytes() == content
    assert saved.name == "report.pdf"


def test_download_multiple_docs(tmp_path):
    from deerflow.tools.adapters.ragflow.download import _do_download

    mock_mcp = _make_download_mcp(b"data")
    output_dir = tmp_path / "out"

    result_str = _do_download(
        doc_ids=["doc-1", "doc-2"],
        output_dir=str(output_dir),
        filenames=["a.pdf", "b.docx"],
        download_mcp=mock_mcp,
    )

    saved_paths = json.loads(result_str)
    assert len(saved_paths) == 2
    assert mock_mcp.invoke.call_count == 2


def test_download_falls_back_to_doc_id_as_filename(tmp_path):
    from deerflow.tools.adapters.ragflow.download import _do_download

    mock_mcp = _make_download_mcp(b"data")
    output_dir = tmp_path / "out"

    result_str = _do_download(
        doc_ids=["doc-abc"],
        output_dir=str(output_dir),
        filenames=None,
        download_mcp=mock_mcp,
    )

    saved_paths = json.loads(result_str)
    assert Path(saved_paths[0]).name == "doc-abc"


def test_download_creates_output_dir_if_missing(tmp_path):
    from deerflow.tools.adapters.ragflow.download import _do_download

    mock_mcp = _make_download_mcp(b"x")
    output_dir = tmp_path / "nested" / "dir"
    assert not output_dir.exists()

    _do_download(["doc-1"], str(output_dir), ["f.txt"], mock_mcp)

    assert output_dir.exists()


def test_make_download_tool_returns_basetool():
    from langchain.tools import BaseTool

    from deerflow.tools.adapters.ragflow.download import make_download_tool

    tool = make_download_tool(MagicMock())
    assert isinstance(tool, BaseTool)
    assert tool.name == "ragflow_download"
    assert "runtime" not in tool.args


def test_make_download_tool_translates_virtual_output_dir(tmp_path):
    """make_download_tool wrapper must resolve /mnt/user-data/ virtual output_dir."""
    import base64
    import json
    from types import SimpleNamespace

    from deerflow.tools.adapters.ragflow.download import make_download_tool

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    thread_data = {
        "workspace_path": str(workspace),
        "uploads_path": str(tmp_path / "uploads"),
        "outputs_path": str(tmp_path / "outputs"),
    }
    runtime = SimpleNamespace(state={"thread_data": thread_data}, context={})

    content = b"file bytes"
    mock_mcp = MagicMock()
    mock_mcp.invoke.return_value = json.dumps({"content_base64": base64.b64encode(content).decode()})
    tool = make_download_tool(mock_mcp)

    result = tool.func(
        runtime=runtime,
        doc_ids=["doc-1"],
        output_dir="/mnt/user-data/workspace",
        filenames=["report.pdf"],
    )

    # File must be saved inside actual workspace dir
    saved = workspace / "report.pdf"
    assert saved.exists()
    assert saved.read_bytes() == content
    # Returned path must be virtual (masked)
    assert "/mnt/user-data" in result
