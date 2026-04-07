"""
FastAPI Application Factory for Langly.

This module provides the main FastAPI application with all middleware,
routes, and lifecycle management configured.
"""
from __future__ import annotations

import asyncio
import logging
from time import perf_counter
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import Settings, get_settings
from app.core.constants import AGENT_MODEL_MAPPING, GRANITE_MODELS, MODEL_FALLBACKS


logger = logging.getLogger(__name__)


# =============================================================================
# Application Lifespan
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Manage application lifecycle.

    This context manager handles startup and shutdown events for the
    FastAPI application.

    Args:
        app: The FastAPI application instance.

    Yields:
        None during application runtime.
    """
    # Startup
    logger.info("Starting Langly Multi-Agent Platform...")

    settings = get_settings()
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")

    async def _ensure_ollama_models() -> None:
        settings = get_settings()
        if not settings.ollama_prefetch_models and not settings.ollama_preload_models:
            logger.info("Ollama model prefetch/preload disabled")
            return

        model_keys = set(AGENT_MODEL_MAPPING.values())
        for key, fallbacks in MODEL_FALLBACKS.items():
            model_keys.add(key)
            model_keys.update(fallbacks)
        required_models = {
            GRANITE_MODELS.get(key, key) for key in model_keys
        }

        if not required_models:
            logger.info("No Ollama models configured for prefetch")
            return

        import httpx

        start = perf_counter()
        try:
            async with httpx.AsyncClient(
                base_url=settings.ollama_host,
                timeout=settings.ollama_timeout,
            ) as client:
                tags_resp = await client.get("/api/tags")
                tags_resp.raise_for_status()
                data = tags_resp.json()
                available = {m.get("name") for m in data.get("models", [])}
                missing = sorted(m for m in required_models if m not in available)

                if settings.ollama_prefetch_models and missing:
                    logger.warning(
                        "Ollama missing models: %s (pulling)",
                        ", ".join(missing),
                    )
                    for model in missing:
                        try:
                            pull_resp = await client.post(
                                "/api/pull",
                                json={"model": model, "stream": False},
                            )
                            pull_resp.raise_for_status()
                        except Exception as exc:
                            logger.warning("Ollama pull failed for %s: %s", model, exc)

                if settings.ollama_preload_models:
                    for model in sorted(required_models):
                        try:
                            warm_resp = await client.post(
                                "/api/chat",
                                json={
                                    "model": model,
                                    "messages": [
                                        {"role": "user", "content": "ping"}
                                    ],
                                    "stream": False,
                                    "keep_alive": settings.ollama_keep_alive,
                                },
                            )
                            warm_resp.raise_for_status()
                        except Exception as exc:
                            logger.warning("Ollama warmup failed for %s: %s", model, exc)
        except Exception as exc:
            logger.warning("Ollama model check failed: %s", exc)
        finally:
            elapsed = perf_counter() - start
            logger.info("Ollama model check finished in %.2fs", elapsed)

    asyncio.create_task(_ensure_ollama_models())

    logger.info("Langly startup complete")

    yield

    # Shutdown
    logger.info("Shutting down Langly...")

    # Cleanup resources
    try:
        # Close Neo4j connections if initialized
        from app.memory.neo4j_client import get_neo4j_client
        neo4j_client = get_neo4j_client()
        if neo4j_client._driver is not None:
            await neo4j_client.close()
            logger.info("Neo4j connection closed")
    except Exception as e:
        logger.warning(f"Error closing Neo4j: {e}")

    logger.info("Langly shutdown complete")


# =============================================================================
# Application Factory
# =============================================================================


def create_app(settings: Settings | None = None) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        settings: Optional settings instance. If not provided,
            settings will be loaded from environment.

    Returns:
        Configured FastAPI application.
    """
    if settings is None:
        settings = get_settings()

    # Configure logging
    log_level = logging.DEBUG if settings.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create application
    app = FastAPI(
        title=settings.app_name,
        description=(
            "A production-grade, parallel multi-agent coding platform "
            "using LangChain, LangGraph, and IBM Granite models."
        ),
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
    )

    # Store settings in app state
    app.state.settings = settings

    # ==========================================================================
    # Middleware
    # ==========================================================================

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ==========================================================================
    # Routes - Lazy Import to Avoid Circular Dependencies
    # ==========================================================================

    from app.api.routes.agents import router as agents_router
    from app.api.routes.chat import router as chat_router
    from app.api.routes.health import router as health_router
    from app.api.routes.websocket import router as websocket_router
    from app.api.routes.workflows import router as workflows_router
    from app.api.routes.workflows_v2 import router as workflows_v2_router
    from app.api.routes.hitl_v2 import router as hitl_v2_router
    from app.api.routes.events_v2 import router as events_v2_router
    from app.api.routes.runs_v2 import router as runs_v2_router
    from app.api.routes.dashboard_v2 import router as dashboard_v2_router
    from app.api.routes.timeline_v2 import router as timeline_v2_router
    from app.api.routes.snapshots_v2 import router as snapshots_v2_router
    from app.api.routes.recent_v2 import router as recent_v2_router
    from app.api.routes.health_v2 import router as health_v2_router
    from app.api.routes.seed_v2 import router as seed_v2_router
    from app.api.routes.status_v2 import router as status_v2_router
    from app.api.routes.config_v2 import router as config_v2_router
    from app.api.routes.overview_v2 import router as overview_v2_router
    from app.api.routes.metrics_v2 import router as metrics_v2_router
    from app.api.routes.reset_v2 import router as reset_v2_router
    from app.api.routes.cleanup_v2 import router as cleanup_v2_router
    from app.api.routes.diagnostics_v2 import router as diagnostics_v2_router
    from app.api.routes.summary_v2 import router as summary_v2_router
    from app.api.routes.models_v2 import router as models_v2_router
    from app.api.routes.neo4j_v2 import router as neo4j_v2_router
    from app.api.routes.docs_v2 import router as docs_v2_router
    from app.api.routes.tools_v2 import router as tools_v2_router
    from app.api.routes.files_v2 import router as files_v2_router
    from app.api.routes.notes_v2 import router as notes_v2_router
    from app.api.routes.agents_v2 import router as agents_v2_router
    from app.api.routes.sessions_v2 import router as sessions_v2_router
    from app.api.routes.harness_v2 import router as harness_v2_router
    from app.api.routes.workflows_v3 import router as workflows_v3_router
    from app.api.routes.runs_v3 import router as runs_v3_router
    from app.api.routes.events_v3 import router as events_v3_router
    from app.api.routes.tools_v3 import router as tools_v3_router
    from app.api.routes.hitl_v3 import router as hitl_v3_router

    # API routes
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(workflows_router, prefix="/api/v1")
    app.include_router(agents_router, prefix="/api/v1")
    app.include_router(chat_router, prefix="/api/v1")
    app.include_router(workflows_v2_router, prefix="/api/v2")
    app.include_router(hitl_v2_router, prefix="/api/v2")
    app.include_router(events_v2_router, prefix="/api/v2")
    app.include_router(agents_v2_router, prefix="/api/v2")
    app.include_router(sessions_v2_router, prefix="/api/v2")
    app.include_router(harness_v2_router, prefix="/api/v2")
    app.include_router(runs_v2_router, prefix="/api/v2")
    app.include_router(dashboard_v2_router, prefix="/api/v2")
    app.include_router(timeline_v2_router, prefix="/api/v2")
    app.include_router(snapshots_v2_router, prefix="/api/v2")
    app.include_router(recent_v2_router, prefix="/api/v2")
    app.include_router(health_v2_router, prefix="/api/v2")
    app.include_router(seed_v2_router, prefix="/api/v2")
    app.include_router(status_v2_router, prefix="/api/v2")
    app.include_router(config_v2_router, prefix="/api/v2")
    app.include_router(overview_v2_router, prefix="/api/v2")
    app.include_router(metrics_v2_router, prefix="/api/v2")
    app.include_router(reset_v2_router, prefix="/api/v2")
    app.include_router(cleanup_v2_router, prefix="/api/v2")
    app.include_router(diagnostics_v2_router, prefix="/api/v2")
    app.include_router(summary_v2_router, prefix="/api/v2")
    app.include_router(models_v2_router, prefix="/api/v2")
    app.include_router(neo4j_v2_router, prefix="/api/v2")
    app.include_router(docs_v2_router, prefix="/api/v2")
    app.include_router(tools_v2_router, prefix="/api/v2")
    app.include_router(files_v2_router, prefix="/api/v2")
    app.include_router(notes_v2_router, prefix="/api/v2")
    app.include_router(workflows_v3_router, prefix="/api/v3")
    app.include_router(runs_v3_router, prefix="/api/v3")
    app.include_router(tools_v3_router, prefix="/api/v3")
    app.include_router(hitl_v3_router, prefix="/api/v3")
    app.include_router(events_v3_router, prefix="/api/v3")

    # WebSocket routes (no /api/v1 prefix for cleaner WS URLs)
    app.include_router(websocket_router)

    # ==========================================================================
    # Static Files (for existing frontend wireframe)
    # ==========================================================================

    # Mount static files directory for frontend assets
    try:
        app.mount("/static", StaticFiles(directory="static"), name="static")
        logger.info("Static files directory mounted at /static")
    except RuntimeError as e:
        logger.warning(f"Could not mount static files: {e}")

    # ==========================================================================
    # Exception Handlers
    # ==========================================================================

    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """Handle all unhandled exceptions."""
        logger.exception(f"Unhandled exception: {exc}")

        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "message": "An unexpected error occurred",
                "detail": str(exc) if settings.debug else None,
            },
        )

    return app


# =============================================================================
# Default Application Instance
# =============================================================================

# Create default application instance for uvicorn
app = create_app()


# =============================================================================
# Development Entry Point
# =============================================================================


def run_dev() -> None:
    """Run the development server."""
    import uvicorn

    settings = get_settings()

    uvicorn.run(
        "app.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
    )


if __name__ == "__main__":
    run_dev()
