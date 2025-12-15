"""
LLM Module for IBM Granite Integration.

This module provides comprehensive LLM functionality including:
- Ollama client for model interaction
- Model registry and configuration
- LLM provider factory for LangChain integration
- Granite Guardian for safety validation
- Embedding client for semantic memory
"""
from app.llm.embeddings import (
    GraniteEmbeddingClient,
    SemanticSearch,
    cosine_similarity,
    embed_text,
    embed_texts,
    euclidean_distance,
    find_most_similar,
    get_embedding_client,
)
from app.llm.guardian import (
    GraniteGuardian,
    RiskLevel,
    SafetyCategory,
    SafetyResult,
    check_for_dangerous_patterns,
    get_guardian,
    validate_before_execution,
)
from app.llm.models import (
    GRANITE_MODEL_REGISTRY,
    ModelCapability,
    ModelConfig,
    ModelSize,
    get_fallback_models,
    get_first_fallback,
    get_model_config,
    get_model_for_agent,
    get_model_options,
    get_models_by_capability,
    get_models_by_size,
    get_recommended_model,
    list_available_models,
)
from app.llm.ollama_client import (
    OllamaClient,
    check_ollama_health,
    ensure_model_available,
    get_ollama_client,
)
from app.llm.provider import (
    GraniteChatModel,
    LLMProvider,
    create_chat_model,
    create_code_model,
    create_general_model,
    create_routing_model,
    get_llm_for_agent,
    get_provider,
)


__all__ = [
    # Ollama Client
    "OllamaClient",
    "get_ollama_client",
    "check_ollama_health",
    "ensure_model_available",
    # Model Registry
    "ModelCapability",
    "ModelConfig",
    "ModelSize",
    "GRANITE_MODEL_REGISTRY",
    "get_model_config",
    "get_model_for_agent",
    "get_fallback_models",
    "get_first_fallback",
    "get_models_by_capability",
    "get_models_by_size",
    "get_recommended_model",
    "get_model_options",
    "list_available_models",
    # LLM Provider
    "GraniteChatModel",
    "LLMProvider",
    "get_provider",
    "get_llm_for_agent",
    "create_chat_model",
    "create_code_model",
    "create_routing_model",
    "create_general_model",
    # Guardian
    "GraniteGuardian",
    "SafetyCategory",
    "RiskLevel",
    "SafetyResult",
    "get_guardian",
    "check_for_dangerous_patterns",
    "validate_before_execution",
    # Embeddings
    "GraniteEmbeddingClient",
    "SemanticSearch",
    "get_embedding_client",
    "embed_text",
    "embed_texts",
    "cosine_similarity",
    "euclidean_distance",
    "find_most_similar",
]
