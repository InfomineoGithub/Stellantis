"""Adapter configuration endpoints for the gateway API."""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from deerflow.config.extensions_config import (
    AdapterConfig,
    ExtensionsConfig,
    get_extensions_config,
    reload_extensions_config,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["adapters"])


class AdapterConfigResponse(BaseModel):
    enabled: bool = Field(default=False)
    wraps_server: str | None = Field(default=None)
    hide_wrapped_tools: bool = Field(default=False)
    tool_mappings: dict[str, str] = Field(default_factory=dict)


class AdaptersConfigResponse(BaseModel):
    adapters: dict[str, AdapterConfigResponse] = Field(default_factory=dict)


class AdaptersConfigUpdateRequest(BaseModel):
    adapters: dict[str, AdapterConfigResponse] = Field(default_factory=dict)


def _config_to_response(config: ExtensionsConfig) -> AdaptersConfigResponse:
    return AdaptersConfigResponse(adapters={name: AdapterConfigResponse(**adapter.model_dump()) for name, adapter in config.adapters.items()})


@router.get("/adapters/config", response_model=AdaptersConfigResponse)
async def get_adapters_configuration() -> AdaptersConfigResponse:
    """Return current adapter configuration loaded from extensions_config.json."""
    return _config_to_response(get_extensions_config())


@router.put("/adapters/config", response_model=AdaptersConfigResponse)
async def update_adapters_configuration(
    request: AdaptersConfigUpdateRequest,
) -> AdaptersConfigResponse:
    """Persist adapter configuration to extensions_config.json (preserving mcpServers/skills)."""
    try:
        config_path = ExtensionsConfig.resolve_config_path()
        if config_path is None:
            config_path = Path.cwd().parent / "extensions_config.json"
            logger.info(f"No existing extensions config found. Creating new config at: {config_path}")

        current = get_extensions_config()
        config_data = {
            "mcpServers": {name: server.model_dump() for name, server in current.mcp_servers.items()},
            "skills": {name: {"enabled": skill.enabled} for name, skill in current.skills.items()},
            "adapters": {name: adapter.model_dump() for name, adapter in request.adapters.items()},
        }

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)

        logger.info(f"Adapter configuration updated and saved to: {config_path}")

        # Validate by constructing AdapterConfig instances (will raise on bad shape)
        for adapter in request.adapters.values():
            AdapterConfig(**adapter.model_dump())

        reloaded = reload_extensions_config()
        return _config_to_response(reloaded)
    except Exception as exc:
        logger.exception("Failed to update adapter configuration")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
