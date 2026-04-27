from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_detect_type_pdf():
    from deerflow.tools.adapters.fetch_url.tool import _detect_type

    assert _detect_type("https://example.com/report.pdf") == "pdf"


def test_detect_type_docx():
    from deerflow.tools.adapters.fetch_url.tool import _detect_type

    assert _detect_type("https://example.com/doc.docx") == "docx"


def test_detect_type_xlsx():
    from deerflow.tools.adapters.fetch_url.tool import _detect_type

    assert _detect_type("https://example.com/sheet.xlsx") == "xlsx"


def test_detect_type_pptx():
    from deerflow.tools.adapters.fetch_url.tool import _detect_type

    assert _detect_type("https://example.com/slide.pptx") == "pptx"


def test_detect_type_webpage_default():
    from deerflow.tools.adapters.fetch_url.tool import _detect_type

    assert _detect_type("https://example.com/page") == "webpage"
    assert _detect_type("https://example.com/") == "webpage"
    assert _detect_type("https://example.com/page.html") == "webpage"


def test_fetch_webpage_saves_markdown(tmp_path):
    from deerflow.tools.adapters.fetch_url.tool import _do_fetch

    mock_mcp = MagicMock()
    mock_mcp.invoke.return_value = "# Hello\nSome content."
    output_dir = tmp_path / "out"

    result = _do_fetch(
        url="https://example.com/page",
        output_dir=str(output_dir),
        content_type=None,
        webpage_mcp=mock_mcp,
    )

    assert result.endswith(".md")
    assert Path(result).read_text() == "# Hello\nSome content."
    mock_mcp.invoke.assert_called_once_with({"url": "https://example.com/page"})


def test_fetch_webpage_type_hint_overrides_detection(tmp_path):
    from deerflow.tools.adapters.fetch_url.tool import _do_fetch

    mock_mcp = MagicMock()
    mock_mcp.invoke.return_value = "markdown content"

    # URL looks like PDF but type hint says webpage
    result = _do_fetch(
        url="https://example.com/report.pdf",
        output_dir=str(tmp_path),
        content_type="webpage",
        webpage_mcp=mock_mcp,
    )

    assert result.endswith(".md")
    mock_mcp.invoke.assert_called_once()


def test_fetch_file_download_saves_bytes(tmp_path):

    from deerflow.tools.adapters.fetch_url.tool import _do_fetch

    mock_mcp = MagicMock()
    output_dir = tmp_path / "files"

    mock_response = MagicMock()
    mock_response.headers = {}
    mock_response.content = b"pdf bytes here"
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_response

        result = _do_fetch(
            url="https://example.com/report.pdf",
            output_dir=str(output_dir),
            content_type="pdf",
            webpage_mcp=mock_mcp,
        )

    assert Path(result).name == "report.pdf"
    assert Path(result).read_bytes() == b"pdf bytes here"


def test_fetch_file_download_uses_content_disposition_filename(tmp_path):

    from deerflow.tools.adapters.fetch_url.tool import _do_fetch

    mock_mcp = MagicMock()
    output_dir = tmp_path / "files"

    mock_response = MagicMock()
    mock_response.headers = {"Content-Disposition": 'attachment; filename="server_name.pdf"'}
    mock_response.content = b"data"
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_response

        result = _do_fetch(
            url="https://example.com/download",
            output_dir=str(output_dir),
            content_type="pdf",
            webpage_mcp=mock_mcp,
        )

    assert Path(result).name == "server_name.pdf"


def test_fetch_video_raises_not_implemented(tmp_path):
    from deerflow.tools.adapters.fetch_url.tool import _do_fetch

    with pytest.raises(NotImplementedError, match="Video transcript not yet supported"):
        _do_fetch(
            url="https://youtube.com/watch?v=abc",
            output_dir=str(tmp_path),
            content_type="video",
            webpage_mcp=MagicMock(),
        )


def test_make_fetch_url_tool_returns_basetool():
    from langchain.tools import BaseTool

    from deerflow.tools.adapters.fetch_url.tool import make_fetch_url_tool

    tool = make_fetch_url_tool(MagicMock())
    assert isinstance(tool, BaseTool)
    assert tool.name == "fetch_url"
    assert "runtime" not in tool.args


def test_make_fetch_url_tool_translates_virtual_output_dir(tmp_path):
    """make_fetch_url_tool wrapper must resolve /mnt/user-data/ virtual output_dir."""
    from types import SimpleNamespace

    from deerflow.tools.adapters.fetch_url.tool import make_fetch_url_tool

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    thread_data = {
        "workspace_path": str(workspace),
        "uploads_path": str(tmp_path / "uploads"),
        "outputs_path": str(tmp_path / "outputs"),
    }
    runtime = SimpleNamespace(state={"thread_data": thread_data}, context={})

    mock_mcp = MagicMock()
    mock_mcp.invoke.return_value = "# Page content"
    tool = make_fetch_url_tool(mock_mcp)

    result = tool.func(
        runtime=runtime,
        url="https://example.com/page",
        output_dir="/mnt/user-data/workspace",
        type="webpage",
    )

    # File must be saved inside actual workspace dir
    saved_files = list(workspace.glob("*.md"))
    assert len(saved_files) == 1
    assert saved_files[0].read_text() == "# Page content"
    # Returned path must be virtual (masked)
    assert "/mnt/user-data" in result
