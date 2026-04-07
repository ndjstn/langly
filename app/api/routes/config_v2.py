"""Config endpoint for v2 runtime."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings
from app.core.constants import AGENT_MODEL_MAPPING, GRANITE_MODELS


router = APIRouter(prefix="/config", tags=["config-v2"])


class ConfigResponse(BaseModel):
    """Config response for v2 runtime."""

    settings: dict
    model_mapping: dict
    models: dict


@router.get("/", response_model=ConfigResponse)
async def config_v2() -> ConfigResponse:
    settings = get_settings()
    return ConfigResponse(
        settings={
            "app_name": settings.app_name,
            "debug": settings.debug,
            "ollama_host": settings.ollama_host,
            "enable_neo4j_memory": settings.enable_neo4j_memory,
        },
        model_mapping=AGENT_MODEL_MAPPING,
        models=GRANITE_MODELS,
    )
