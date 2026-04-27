import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from deerflow.config.extensions_config import ExtensionsConfig


def _make_config_with_adapters():
    return ExtensionsConfig.model_validate(
        {
            "mcpServers": {},
            "adapters": {
                "ragflow_builtin": {
                    "enabled": False,
                    "wraps_server": "ragflow",
                    "hide_wrapped_tools": False,
                    "tool_mappings": {"upload": "ragflow__upload_with_metadata"},
                }
            },
        }
    )


def test_get_adapters_config_returns_adapter_list(tmp_path):
    from app.gateway.app import app

    mock_config = _make_config_with_adapters()
    with patch("app.gateway.routers.adapters.get_extensions_config", return_value=mock_config), patch("app.gateway.dependencies.get_current_user", return_value={"id": "user-1"}):
        client = TestClient(app)
        response = client.get("/api/adapters/config")

    assert response.status_code == 200
    data = response.json()
    assert "ragflow_builtin" in data["adapters"]
    assert data["adapters"]["ragflow_builtin"]["enabled"] is False


def test_put_adapters_config_writes_file(tmp_path):
    from app.gateway.app import app

    config_file = tmp_path / "extensions_config.json"
    config_file.write_text(
        json.dumps(
            {
                "mcpServers": {},
                "skills": {},
                "adapters": {
                    "ragflow_builtin": {
                        "enabled": False,
                        "wraps_server": "ragflow",
                        "hide_wrapped_tools": False,
                        "tool_mappings": {},
                    }
                },
            }
        )
    )
    mock_config = _make_config_with_adapters()

    with (
        patch("app.gateway.routers.adapters.get_extensions_config", return_value=mock_config),
        patch("app.gateway.routers.adapters.reload_extensions_config", return_value=mock_config),
        patch("app.gateway.routers.adapters.ExtensionsConfig.resolve_config_path", return_value=config_file),
        patch("app.gateway.dependencies.get_current_user", return_value={"id": "user-1"}),
    ):
        client = TestClient(app)
        response = client.put(
            "/api/adapters/config",
            json={
                "adapters": {
                    "ragflow_builtin": {
                        "enabled": True,
                        "wraps_server": "ragflow",
                        "hide_wrapped_tools": False,
                        "tool_mappings": {"upload": "ragflow__upload_with_metadata"},
                    }
                }
            },
        )

    assert response.status_code == 200
