"""Models endpoint for v2 runtime."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.constants import AGENT_MODEL_MAPPING, GRANITE_MODELS, MODEL_FALLBACKS


router = APIRouter(prefix="/models", tags=["models-v2"])


class ModelsResponse(BaseModel):
    """Models mapping response."""

    model_mapping: dict
    models: dict
    fallbacks: dict


@router.get("/", response_model=ModelsResponse)
async def models_v2() -> ModelsResponse:
    return ModelsResponse(
        model_mapping=AGENT_MODEL_MAPPING,
        models=GRANITE_MODELS,
        fallbacks=MODEL_FALLBACKS,
    )
