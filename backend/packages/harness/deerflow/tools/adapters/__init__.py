import importlib

from langchain.tools import BaseTool

from deerflow.config.extensions_config import ExtensionsConfig

ADAPTER_REGISTRY: dict[str, str] = {
    "ragflow_builtin": "deerflow.tools.adapters.ragflow",
    "fetch_url": "deerflow.tools.adapters.fetch_url",
    "fetch_webpage": "deerflow.tools.adapters.fetch_webpage",
}


def load_adapter_tools(
    extensions_config: ExtensionsConfig,
    mcp_tools: list[BaseTool],
) -> tuple[list[BaseTool], list[BaseTool]]:
    """Return (adapter_tools, visible_mcp_tools).

    visible_mcp_tools is mcp_tools with wrapped-server tools removed
    for any adapter that has hide_wrapped_tools=True.
    """
    adapter_tools: list[BaseTool] = []
    visible_mcp_tools: list[BaseTool] = list(mcp_tools)

    for adapter_name, adapter_config in extensions_config.adapters.items():
        if not adapter_config.enabled:
            continue

        module_path = ADAPTER_REGISTRY.get(adapter_name)
        if module_path is None:
            continue

        module = importlib.import_module(module_path)
        adapter_tools.extend(module.get_tools(adapter_config, mcp_tools))

        if adapter_config.hide_wrapped_tools:
            for mcp_tool_name in adapter_config.tool_mappings.values():
                visible_mcp_tools = [t for t in visible_mcp_tools if t.name != mcp_tool_name]
    return adapter_tools, visible_mcp_tools
