"""
IBM Granite Model Registry.

This module defines the IBM Granite model family configurations
and provides utilities for model selection and management.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.core.constants import (
    AGENT_MODEL_MAPPING,
    GRANITE_MODELS,
    MODEL_FALLBACKS,
)


logger = logging.getLogger(__name__)


class ModelCapability(str, Enum):
    """Model capability categories."""

    GENERAL = "general"
    CODE = "code"
    ROUTING = "routing"
    SAFETY = "safety"
    EMBEDDING = "embedding"
    FUNCTION_CALLING = "function_calling"


class ModelSize(str, Enum):
    """Model size categories."""

    TINY = "tiny"  # < 1B parameters
    SMALL = "small"  # 1-3B parameters
    MEDIUM = "medium"  # 3-8B parameters
    LARGE = "large"  # 8B+ parameters


@dataclass
class ModelConfig:
    """Configuration for a specific model.

    Attributes:
        name: Ollama model name.
        display_name: Human-readable name.
        capabilities: List of model capabilities.
        size: Model size category.
        context_length: Maximum context window size.
        recommended_for: List of recommended use cases.
        default_temperature: Default temperature for generation.
        default_top_p: Default top_p for sampling.
        supports_tools: Whether model supports tool/function calling.
        description: Model description.
    """

    name: str
    display_name: str
    capabilities: list[ModelCapability] = field(default_factory=list)
    size: ModelSize = ModelSize.MEDIUM
    context_length: int = 8192
    recommended_for: list[str] = field(default_factory=list)
    default_temperature: float = 0.7
    default_top_p: float = 0.9
    supports_tools: bool = False
    description: str = ""


# IBM Granite Model Registry
GRANITE_MODEL_REGISTRY: dict[str, ModelConfig] = {
    # Dense Models - General Purpose
    GRANITE_MODELS["dense_2b"]: ModelConfig(
        name=GRANITE_MODELS["dense_2b"],
        display_name="Granite 3.1 Dense 2B",
        capabilities=[
            ModelCapability.GENERAL,
            ModelCapability.FUNCTION_CALLING,
        ],
        size=ModelSize.SMALL,
        context_length=8192,
        recommended_for=["quick tasks", "low latency", "simple queries"],
        default_temperature=0.7,
        supports_tools=True,
        description=(
            "Fast, efficient model for general tasks "
            "with function calling support."
        ),
    ),
    GRANITE_MODELS["dense_8b"]: ModelConfig(
        name=GRANITE_MODELS["dense_8b"],
        display_name="Granite 3.1 Dense 8B",
        capabilities=[
            ModelCapability.GENERAL,
            ModelCapability.CODE,
            ModelCapability.FUNCTION_CALLING,
        ],
        size=ModelSize.LARGE,
        context_length=8192,
        recommended_for=[
            "complex tasks",
            "code generation",
            "detailed analysis",
        ],
        default_temperature=0.7,
        supports_tools=True,
        description=(
            "High-capability model for complex reasoning "
            "and code generation."
        ),
    ),
    # MoE Models - Fast Routing
    GRANITE_MODELS["moe_1b"]: ModelConfig(
        name=GRANITE_MODELS["moe_1b"],
        display_name="Granite 3.1 MoE 1B",
        capabilities=[ModelCapability.ROUTING, ModelCapability.GENERAL],
        size=ModelSize.TINY,
        context_length=8192,
        recommended_for=["routing", "classification", "low latency"],
        default_temperature=0.3,
        supports_tools=False,
        description=(
            "Ultra-fast MoE model for routing decisions "
            "and quick classification."
        ),
    ),
    GRANITE_MODELS["moe_3b"]: ModelConfig(
        name=GRANITE_MODELS["moe_3b"],
        display_name="Granite 3.1 MoE 3B",
        capabilities=[
            ModelCapability.ROUTING,
            ModelCapability.GENERAL,
            ModelCapability.FUNCTION_CALLING,
        ],
        size=ModelSize.SMALL,
        context_length=8192,
        recommended_for=["routing", "simple tasks", "quick analysis"],
        default_temperature=0.5,
        supports_tools=True,
        description=(
            "Efficient MoE model balancing speed and capability."
        ),
    ),
    # Code Models
    GRANITE_MODELS["code_8b"]: ModelConfig(
        name=GRANITE_MODELS["code_8b"],
        display_name="Granite Code 8B",
        capabilities=[
            ModelCapability.CODE,
            ModelCapability.FUNCTION_CALLING,
        ],
        size=ModelSize.LARGE,
        context_length=8192,
        recommended_for=[
            "code generation",
            "code review",
            "debugging",
            "refactoring",
        ],
        default_temperature=0.2,
        supports_tools=True,
        description=(
            "High-capability code model for complex generation, "
            "review, and analysis tasks."
        ),
    ),
    GRANITE_MODELS["code_3b"]: ModelConfig(
        name=GRANITE_MODELS["code_3b"],
        display_name="Granite Code 3B",
        capabilities=[
            ModelCapability.CODE,
        ],
        size=ModelSize.SMALL,
        context_length=8192,
        recommended_for=[
            "quick code tasks",
            "code completion",
            "simple refactoring",
        ],
        default_temperature=0.2,
        supports_tools=False,
        description=(
            "Fast code model for quick generation and testing tasks."
        ),
    ),
    # Guardian Model - Safety
    GRANITE_MODELS["guardian"]: ModelConfig(
        name=GRANITE_MODELS["guardian"],
        display_name="Granite Guardian",
        capabilities=[ModelCapability.SAFETY],
        size=ModelSize.SMALL,
        context_length=4096,
        recommended_for=[
            "content safety",
            "moderation",
            "policy compliance",
        ],
        default_temperature=0.1,
        supports_tools=False,
        description=(
            "Safety validation model for content moderation "
            "and policy enforcement."
        ),
    ),
    # Embedding Model
    GRANITE_MODELS["embedding"]: ModelConfig(
        name=GRANITE_MODELS["embedding"],
        display_name="Granite Embedding",
        capabilities=[ModelCapability.EMBEDDING],
        size=ModelSize.SMALL,
        context_length=512,
        recommended_for=[
            "semantic search",
            "similarity",
            "retrieval",
        ],
        default_temperature=0.0,
        supports_tools=False,
        description=(
            "Embedding model for semantic similarity "
            "and retrieval tasks."
        ),
    ),
}


def get_model_config(model_name: str) -> ModelConfig | None:
    """
    Get configuration for a specific model.

    Args:
        model_name: Ollama model name.

    Returns:
        Model configuration if found, None otherwise.
    """
    return GRANITE_MODEL_REGISTRY.get(model_name)


def get_model_for_agent(agent_type: str) -> str:
    """
    Get the recommended model for a specific agent type.

    Args:
        agent_type: Type of agent (pm, coder, architect, etc.).

    Returns:
        Recommended model name.
    """
    return AGENT_MODEL_MAPPING.get(
        agent_type,
        GRANITE_MODELS["dense_8b"],  # Default to most capable
    )


def get_fallback_models(model_name: str) -> list[str]:
    """
    Get all fallback models for a given model.

    Args:
        model_name: Primary model name.

    Returns:
        List of fallback model names in priority order, empty if none.
    """
    return MODEL_FALLBACKS.get(model_name, [])


def get_first_fallback(model_name: str) -> str | None:
    """
    Get the first fallback model for a given model.

    Args:
        model_name: Primary model name.

    Returns:
        First fallback model name if defined, None otherwise.
    """
    fallbacks = get_fallback_models(model_name)
    return fallbacks[0] if fallbacks else None


def get_models_by_capability(
    capability: ModelCapability,
) -> list[ModelConfig]:
    """
    Get all models with a specific capability.

    Args:
        capability: The capability to filter by.

    Returns:
        List of model configurations with the capability.
    """
    return [
        config
        for config in GRANITE_MODEL_REGISTRY.values()
        if capability in config.capabilities
    ]


def get_models_by_size(size: ModelSize) -> list[ModelConfig]:
    """
    Get all models of a specific size.

    Args:
        size: The size category to filter by.

    Returns:
        List of model configurations of that size.
    """
    return [
        config
        for config in GRANITE_MODEL_REGISTRY.values()
        if config.size == size
    ]


def get_recommended_model(
    task_type: str,
    prefer_speed: bool = False,
) -> str:
    """
    Get recommended model for a task type.

    Args:
        task_type: Type of task (code, routing, safety, etc.).
        prefer_speed: If True, prefer faster smaller models.

    Returns:
        Recommended model name.
    """
    task_to_capability = {
        "code": ModelCapability.CODE,
        "coding": ModelCapability.CODE,
        "route": ModelCapability.ROUTING,
        "routing": ModelCapability.ROUTING,
        "classify": ModelCapability.ROUTING,
        "safety": ModelCapability.SAFETY,
        "moderate": ModelCapability.SAFETY,
        "embed": ModelCapability.EMBEDDING,
        "search": ModelCapability.EMBEDDING,
        "general": ModelCapability.GENERAL,
        "function": ModelCapability.FUNCTION_CALLING,
    }

    capability = task_to_capability.get(
        task_type.lower(),
        ModelCapability.GENERAL,
    )

    models = get_models_by_capability(capability)

    if not models:
        return GRANITE_MODELS["dense_8b"]

    # Sort by size (smaller first if prefer_speed)
    size_order = {
        ModelSize.TINY: 0,
        ModelSize.SMALL: 1,
        ModelSize.MEDIUM: 2,
        ModelSize.LARGE: 3,
    }

    sorted_models = sorted(
        models,
        key=lambda m: size_order.get(m.size, 2),
        reverse=not prefer_speed,
    )

    return sorted_models[0].name


def get_model_options(
    model_name: str,
    temperature: float | None = None,
    top_p: float | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Get model generation options with defaults from config.

    Args:
        model_name: Model name to get defaults for.
        temperature: Override temperature.
        top_p: Override top_p.
        **kwargs: Additional options.

    Returns:
        Options dictionary for model generation.
    """
    config = get_model_config(model_name)

    options: dict[str, Any] = {}

    if config:
        options["temperature"] = (
            temperature
            if temperature is not None
            else config.default_temperature
        )
        options["top_p"] = (
            top_p if top_p is not None else config.default_top_p
        )
    else:
        options["temperature"] = (
            temperature if temperature is not None else 0.7
        )
        options["top_p"] = top_p if top_p is not None else 0.9

    options.update(kwargs)
    return options


def list_available_models() -> list[dict[str, Any]]:
    """
    List all available models with their info.

    Returns:
        List of model information dictionaries.
    """
    return [
        {
            "name": config.name,
            "display_name": config.display_name,
            "size": config.size.value,
            "capabilities": [c.value for c in config.capabilities],
            "supports_tools": config.supports_tools,
            "description": config.description,
        }
        for config in GRANITE_MODEL_REGISTRY.values()
    ]
