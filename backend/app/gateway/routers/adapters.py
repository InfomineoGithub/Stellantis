import json
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.gateway.dependencies import get_current_user
from deerflow.config.extensions_config import (
    ExtensionsConfig,
    get_extensions_config,
    reload_extensions_config,
)

router = APIRouter(prefix="/api")


class AdapterConfigResponse(BaseModel):
    enabled: bool
    wraps_server: str | None
    hide_wrapped_tools: bool
    tool_mappings: dict[str, str]


class AdaptersConfigResponse(BaseModel):
    adapters: dict[str, AdapterConfigResponse]


class AdaptersConfigUpdateRequest(BaseModel):
    adapters: dict[str, AdapterConfigResponse]


@router.get("/adapters/config", response_model=AdaptersConfigResponse)
async def get_adapters_configuration(
    _user: dict = Depends(get_current_user),
) -> AdaptersConfigResponse:
    config = get_extensions_config()
    return AdaptersConfigResponse(adapters={name: AdapterConfigResponse(**adapter.model_dump()) for name, adapter in config.adapters.items()})


@router.put("/adapters/config", response_model=AdaptersConfigResponse)
async def update_adapters_configuration(
    request: AdaptersConfigUpdateRequest,
    _user: dict = Depends(get_current_user),
) -> AdaptersConfigResponse:
    config_path = ExtensionsConfig.resolve_config_path()
    if config_path is None:
        config_path = Path.cwd().parent / "extensions_config.json"

    current = get_extensions_config()
    config_data = {
        "mcpServers": {name: server.model_dump() for name, server in current.mcp_servers.items()},
        "skills": {name: {"enabled": skill.enabled} for name, skill in current.skills.items()},
        "adapters": {name: adapter.model_dump() for name, adapter in request.adapters.items()},
    }

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)

    reloaded = reload_extensions_config()
    return AdaptersConfigResponse(adapters={name: AdapterConfigResponse(**adapter.model_dump()) for name, adapter in reloaded.adapters.items()})
