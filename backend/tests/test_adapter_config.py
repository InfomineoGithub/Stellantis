from deerflow.config.extensions_config import AdapterConfig, ExtensionsConfig


def test_adapter_config_defaults():
    cfg = AdapterConfig()
    assert cfg.enabled is False
    assert cfg.wraps_server is None
    assert cfg.hide_wrapped_tools is False
    assert cfg.tool_mappings == {}


def test_extensions_config_parses_adapters():
    raw = {
        "mcpServers": {},
        "adapters": {
            "ragflow_builtin": {
                "enabled": True,
                "wraps_server": "ragflow",
                "hide_wrapped_tools": False,
                "tool_mappings": {
                    "upload": "ragflow__upload_with_metadata",
                    "download": "ragflow__download_attachment",
                },
            }
        },
    }
    config = ExtensionsConfig.model_validate(raw)
    assert "ragflow_builtin" in config.adapters
    adapter = config.adapters["ragflow_builtin"]
    assert adapter.enabled is True
    assert adapter.wraps_server == "ragflow"
    assert adapter.tool_mappings["upload"] == "ragflow__upload_with_metadata"


def test_extensions_config_adapters_default_empty():
    raw = {"mcpServers": {}}
    config = ExtensionsConfig.model_validate(raw)
    assert config.adapters == {}
