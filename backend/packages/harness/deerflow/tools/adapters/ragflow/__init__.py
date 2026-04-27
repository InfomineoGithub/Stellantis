from langchain.tools import BaseTool
from deerflow.config.extensions_config import AdapterConfig
from deerflow.tools.adapters.ragflow.upload import make_upload_tool
from deerflow.tools.adapters.ragflow.download import make_download_tool


def get_tools(adapter_config: AdapterConfig, mcp_tools: list[BaseTool]) -> list[BaseTool]:
    mcp_by_name = {t.name: t for t in mcp_tools}

    upload_name = adapter_config.tool_mappings.get("upload")
    download_name = adapter_config.tool_mappings.get("download")

    tools: list[BaseTool] = []

    if upload_name and upload_name in mcp_by_name:
        tools.append(make_upload_tool(mcp_by_name[upload_name]))

    if download_name and download_name in mcp_by_name:
        tools.append(make_download_tool(mcp_by_name[download_name]))

    return tools
