from langchain.tools import BaseTool

from deerflow.config.extensions_config import AdapterConfig
from deerflow.tools.adapters.fetch_webpage.tool import make_fetch_webpage_tool


def get_tools(adapter_config: AdapterConfig, mcp_tools: list[BaseTool]) -> list[BaseTool]:
    mcp_by_name = {t.name: t for t in mcp_tools}
    webpage_name = adapter_config.tool_mappings.get("webpage")

    if not webpage_name or webpage_name not in mcp_by_name:
        return []

    return [make_fetch_webpage_tool(mcp_by_name[webpage_name])]
