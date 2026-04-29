"""Load MCP tools using langchain-mcp-adapters."""

import logging

from langchain_core.tools import BaseTool

from deerflow.config.extensions_config import ExtensionsConfig
from deerflow.mcp.client import build_servers_config
from deerflow.mcp.oauth import build_oauth_tool_interceptor, get_initial_oauth_headers

logger = logging.getLogger(__name__)


def _filter_server_tools(tools: list[BaseTool], extensions_config: ExtensionsConfig) -> list[BaseTool]:
    """Apply per-server include_tools / exclude_tools filters.

    Tool names from MultiServerMCPClient are prefixed as ``{server_name}__{tool_name}``.
    The filter lists in McpServerConfig use the *short* name (without the prefix).
    """
    filtered: list[BaseTool] = []
    for tool in tools:
        server_name: str | None = None
        short_name: str = tool.name
        for name in extensions_config.mcp_servers:
            prefix = f"{name}__"
            if tool.name.startswith(prefix):
                server_name = name
                short_name = tool.name[len(prefix):]
                break

        if server_name is None:
            filtered.append(tool)
            continue

        server_config = extensions_config.mcp_servers[server_name]

        if server_config.include_tools is not None and short_name not in server_config.include_tools:
            logger.debug(f"Excluding tool '{tool.name}' (not in include_tools for server '{server_name}')")
            continue

        if server_config.exclude_tools is not None and short_name in server_config.exclude_tools:
            logger.debug(f"Excluding tool '{tool.name}' (in exclude_tools for server '{server_name}')")
            continue

        filtered.append(tool)
    return filtered


async def get_mcp_tools() -> list[BaseTool]:
    """Get all tools from enabled MCP servers.

    Returns:
        List of LangChain tools from all enabled MCP servers.
    """
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError:
        logger.warning("langchain-mcp-adapters not installed. Install it to enable MCP tools: pip install langchain-mcp-adapters")
        return []

    # NOTE: We use ExtensionsConfig.from_file() instead of get_extensions_config()
    # to always read the latest configuration from disk. This ensures that changes
    # made through the Gateway API (which runs in a separate process) are immediately
    # reflected when initializing MCP tools.
    extensions_config = ExtensionsConfig.from_file()
    servers_config = build_servers_config(extensions_config)

    if not servers_config:
        logger.info("No enabled MCP servers configured")
        return []

    try:
        # Create the multi-server MCP client
        logger.info(f"Initializing MCP client with {len(servers_config)} server(s)")

        # Inject initial OAuth headers for server connections (tool discovery/session init)
        initial_oauth_headers = await get_initial_oauth_headers(extensions_config)
        for server_name, auth_header in initial_oauth_headers.items():
            if server_name not in servers_config:
                continue
            if servers_config[server_name].get("transport") in ("sse", "http"):
                existing_headers = dict(servers_config[server_name].get("headers", {}))
                existing_headers["Authorization"] = auth_header
                servers_config[server_name]["headers"] = existing_headers

        tool_interceptors = []
        oauth_interceptor = build_oauth_tool_interceptor(extensions_config)
        if oauth_interceptor is not None:
            tool_interceptors.append(oauth_interceptor)

        client = MultiServerMCPClient(servers_config, tool_interceptors=tool_interceptors, tool_name_prefix=True)

        # Get all tools from all servers
        tools = await client.get_tools()
        logger.info(f"Successfully loaded {len(tools)} tool(s) from MCP servers")

        # Apply per-server include/exclude filters
        tools = _filter_server_tools(tools, extensions_config)
        logger.info(f"{len(tools)} tool(s) remaining after per-server tool filters")

        return tools

    except Exception as e:
        logger.error(f"Failed to load MCP tools: {e}", exc_info=True)
        return []
