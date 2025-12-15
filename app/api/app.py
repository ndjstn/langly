"""
FastAPI Application Factory for Langly.

This module provides the main FastAPI application with all middleware,
routes, and lifecycle management configured.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import Settings, get_settings


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

    # Initialize services (lazy loaded on first use)
    # Neo4j, Ollama, etc. will initialize when first accessed

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
    from app.api.routes.health import router as health_router
    from app.api.routes.websocket import router as websocket_router
    from app.api.routes.workflows import router as workflows_router

    # API routes
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(workflows_router, prefix="/api/v1")
    app.include_router(agents_router, prefix="/api/v1")

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
