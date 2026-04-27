from unittest.mock import MagicMock, patch

from deerflow.config.extensions_config import AdapterConfig, ExtensionsConfig


def _make_mcp_tool(name: str):
    tool = MagicMock()
    tool.name = name
    return tool


def _make_config(adapters: dict) -> ExtensionsConfig:
    return ExtensionsConfig.model_validate({"mcpServers": {}, "adapters": adapters})


def test_load_adapter_tools_returns_empty_when_no_adapters():
    from deerflow.tools.adapters import load_adapter_tools

    config = _make_config({})
    adapter_tools, visible_mcp = load_adapter_tools(config, [])
    assert adapter_tools == []
    assert visible_mcp == []


def test_load_adapter_tools_skips_disabled_adapters():
    from deerflow.tools.adapters import load_adapter_tools

    config = _make_config({"ragflow_builtin": {"enabled": False, "wraps_server": "ragflow", "tool_mappings": {}}})
    mcp_tools = [_make_mcp_tool("ragflow__upload_with_metadata")]
    adapter_tools, visible_mcp = load_adapter_tools(config, mcp_tools)
    assert adapter_tools == []
    assert len(visible_mcp) == 1  # MCP tool not filtered when adapter disabled


def test_load_adapter_tools_hides_wrapped_tools_when_flag_set():
    from deerflow.tools.adapters import load_adapter_tools

    config = _make_config(
        {
            "ragflow_builtin": {
                "enabled": True,
                "wraps_server": "ragflow",
                "hide_wrapped_tools": True,
                "tool_mappings": {
                    "upload": "ragflow__upload_with_metadata",
                    "download": "ragflow__download_attachment",
                },
            }
        }
    )
    mcp_tools = [
        _make_mcp_tool("ragflow__upload_with_metadata"),
        _make_mcp_tool("ragflow__download_attachment"),
        _make_mcp_tool("cloudflare__browser_render_markdown"),
    ]

    with patch("deerflow.tools.adapters.ragflow.get_tools", return_value=[MagicMock()]):
        adapter_tools, visible_mcp = load_adapter_tools(config, mcp_tools)

    # ragflow__ tools filtered, cloudflare tool kept
    assert all(not t.name.startswith("ragflow__") for t in visible_mcp)
    assert any(t.name == "cloudflare__browser_render_markdown" for t in visible_mcp)


def test_load_adapter_tools_keeps_all_mcp_when_hide_false():
    from deerflow.tools.adapters import load_adapter_tools

    config = _make_config(
        {
            "ragflow_builtin": {
                "enabled": True,
                "wraps_server": "ragflow",
                "hide_wrapped_tools": False,
                "tool_mappings": {
                    "upload": "ragflow__upload_with_metadata",
                    "download": "ragflow__download_attachment",
                },
            }
        }
    )
    mcp_tools = [_make_mcp_tool("ragflow__upload_with_metadata")]

    with patch("deerflow.tools.adapters.ragflow.get_tools", return_value=[]):
        _, visible_mcp = load_adapter_tools(config, mcp_tools)

    assert len(visible_mcp) == 1


def test_load_adapter_tools_skips_unknown_registry_adapters():
    from deerflow.tools.adapters import load_adapter_tools

    config = _make_config({"unknown_adapter": {"enabled": True, "wraps_server": "foo", "tool_mappings": {}}})
    mcp_tools = [_make_mcp_tool("foo__tool")]
    adapter_tools, visible_mcp = load_adapter_tools(config, mcp_tools)
    assert adapter_tools == []
    assert len(visible_mcp) == 1


def test_ragflow_adapter_get_tools_returns_two_tools():
    from deerflow.tools.adapters.ragflow import get_tools

    cfg = AdapterConfig(
        enabled=True,
        wraps_server="ragflow",
        tool_mappings={
            "upload": "ragflow__upload_with_metadata",
            "download": "ragflow__download_attachment",
        },
    )
    mcp_tools = [
        _make_mcp_tool("ragflow__upload_with_metadata"),
        _make_mcp_tool("ragflow__download_attachment"),
    ]
    tools = get_tools(cfg, mcp_tools)
    tool_names = [t.name for t in tools]
    assert "ragflow_upload" in tool_names
    assert "ragflow_download" in tool_names


def test_ragflow_adapter_skips_missing_mcp_tools():
    from deerflow.tools.adapters.ragflow import get_tools

    cfg = AdapterConfig(
        enabled=True,
        tool_mappings={"upload": "ragflow__upload_with_metadata"},
    )
    tools = get_tools(cfg, [])  # no MCP tools available
    assert tools == []


def test_fetch_url_adapter_get_tools_returns_one_tool():
    from deerflow.tools.adapters.fetch_url import get_tools

    cfg = AdapterConfig(
        enabled=True,
        wraps_server="cloudflare",
        tool_mappings={"webpage": "cloudflare__browser_render_markdown"},
    )
    mcp_tools = [_make_mcp_tool("cloudflare__browser_render_markdown")]
    tools = get_tools(cfg, mcp_tools)
    assert len(tools) == 1
    assert tools[0].name == "fetch_url"


def test_fetch_url_adapter_returns_empty_when_mcp_missing():
    from deerflow.tools.adapters.fetch_url import get_tools

    cfg = AdapterConfig(
        enabled=True,
        tool_mappings={"webpage": "cloudflare__browser_render_markdown"},
    )
    tools = get_tools(cfg, [])
    assert tools == []
