import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock


def test_extract_markdown_from_markdown_key():
    from deerflow.tools.adapters.fetch_webpage.tool import _extract_markdown

    raw = json.dumps({"markdown": "# Title\nContent here", "url": "https://example.com"})
    assert _extract_markdown(raw) == "# Title\nContent here"


def test_extract_markdown_fallback_content_key():
    from deerflow.tools.adapters.fetch_webpage.tool import _extract_markdown

    raw = json.dumps({"content": "plain text content", "status": 200})
    assert _extract_markdown(raw) == "plain text content"


def test_extract_markdown_fallback_text_key():
    from deerflow.tools.adapters.fetch_webpage.tool import _extract_markdown

    raw = json.dumps({"text": "text fallback"})
    assert _extract_markdown(raw) == "text fallback"


def test_extract_markdown_plain_string():
    from deerflow.tools.adapters.fetch_webpage.tool import _extract_markdown

    assert _extract_markdown("just a plain string") == "just a plain string"


def test_extract_markdown_list_of_dicts():
    from deerflow.tools.adapters.fetch_webpage.tool import _extract_markdown

    # Real MCP format: list of content blocks wrapping serper's JSON payload
    inner_json = json.dumps({"markdown": "# From list", "text": "plain text", "url": "x"})
    raw = json.dumps([{"type": "text", "text": inner_json}])
    assert _extract_markdown(raw) == "# From list"


def test_extract_markdown_mcp_wrapper_nested_json():
    from deerflow.tools.adapters.fetch_webpage.tool import _extract_markdown

    # Simulates exact serper MCP ainvoke return value (list, not JSON string)
    inner_json = json.dumps({"markdown": "# Real markdown", "text": "plain", "metadata": {}})
    raw = [{"type": "text", "text": inner_json}]
    assert _extract_markdown(raw) == "# Real markdown"


def test_extract_markdown_dict_no_known_key():
    from deerflow.tools.adapters.fetch_webpage.tool import _extract_markdown

    raw = json.dumps({"unknown_key": "value"})
    result = _extract_markdown(raw)
    # Should fall back to json.dumps of the dict
    assert "unknown_key" in result


async def test_do_fetch_extended_webpage_saves_markdown(tmp_path):
    from deerflow.tools.adapters.fetch_webpage.tool import _do_fetch_extended

    mock_mcp = AsyncMock()
    # Simulate real serper MCP response: list wrapping a JSON payload with "markdown" key
    inner_json = json.dumps({"markdown": "# Hello\nSome content.", "text": "plain"})
    mock_mcp.ainvoke.return_value = [{"type": "text", "text": inner_json}]
    output_dir = tmp_path / "out"

    result = await _do_fetch_extended(
        url="https://example.com/page",
        output_dir=str(output_dir),
        webpage_scrape_mcp=mock_mcp,
    )

    assert result.endswith(".md")
    assert Path(result).read_text() == "# Hello\nSome content."
    mock_mcp.ainvoke.assert_called_once_with({"url": "https://example.com/page", "includeMarkdown": True})


async def test_do_fetch_extended_passes_include_markdown(tmp_path):
    from deerflow.tools.adapters.fetch_webpage.tool import _do_fetch_extended

    mock_mcp = AsyncMock()
    mock_mcp.ainvoke.return_value = "plain markdown string"

    await _do_fetch_extended(
        url="https://example.com/page",
        output_dir=str(tmp_path),
        webpage_scrape_mcp=mock_mcp,
    )

    call_args = mock_mcp.ainvoke.call_args[0][0]
    assert call_args["includeMarkdown"] is True


def test_make_fetch_webpage_tool_returns_basetool():
    from langchain.tools import BaseTool

    from deerflow.tools.adapters.fetch_webpage.tool import make_fetch_webpage_tool

    tool = make_fetch_webpage_tool(MagicMock())
    assert isinstance(tool, BaseTool)
    assert tool.name == "fetch_webpage"
    assert "runtime" not in tool.args
    assert "type" not in tool.args


async def test_make_fetch_webpage_tool_translates_virtual_output_dir(tmp_path):
    """make_fetch_webpage_tool wrapper must resolve /mnt/user-data/ virtual output_dir."""
    from deerflow.tools.adapters.fetch_webpage.tool import make_fetch_webpage_tool

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    thread_data = {
        "workspace_path": str(workspace),
        "uploads_path": str(tmp_path / "uploads"),
        "outputs_path": str(tmp_path / "outputs"),
    }
    runtime = SimpleNamespace(state={"thread_data": thread_data}, context={})

    mock_mcp = AsyncMock()
    mock_mcp.ainvoke.return_value = json.dumps({"markdown": "# Page content"})
    fetcher = make_fetch_webpage_tool(mock_mcp)

    result = await fetcher.coroutine(
        runtime=runtime,
        url="https://example.com/page",
        output_dir="/mnt/user-data/workspace",
    )

    saved_files = list(workspace.glob("*.md"))
    assert len(saved_files) == 1
    assert saved_files[0].read_text() == "# Page content"
    assert "/mnt/user-data" in result
