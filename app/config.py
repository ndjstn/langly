"""
Configuration management using pydantic-settings.

This module provides centralized configuration for the Langly platform,
loading settings from environment variables with sensible defaults.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Attributes:
        app_name: Application name for display purposes.
        app_host: Host address for the FastAPI server.
        app_port: Port number for the FastAPI server.
        debug: Enable debug mode for development.
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        ollama_host: Ollama server URL.
        neo4j_uri: Neo4j database connection URI.
        neo4j_user: Neo4j database username.
        neo4j_password: Neo4j database password.
        max_iterations: Maximum workflow iterations before timeout.
        default_timeout: Default timeout in seconds for operations.
        cors_origins: Allowed CORS origins as comma-separated list.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application settings
    app_name: str = Field(default="Langly", description="Application name")
    app_host: str = Field(default="0.0.0.0", description="Server host")
    app_port: int = Field(default=8000, description="Server port")
    debug: bool = Field(default=True, description="Debug mode")
    environment: Literal[
        "development", "staging", "production"
    ] = Field(default="development", description="Environment name")
    log_level: Literal[
        "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
    ] = Field(default="DEBUG", description="Logging level")

    # Ollama settings
    ollama_host: str = Field(
        default="http://localhost:11434",
        description="Ollama server URL"
    )
    ollama_timeout: int = Field(
        default=120,
        description="Ollama request timeout in seconds"
    )

    # Neo4j settings
    neo4j_uri: str = Field(
        default="bolt://localhost:7687",
        description="Neo4j connection URI"
    )
    neo4j_user: str = Field(
        default="neo4j",
        description="Neo4j username"
    )
    neo4j_password: str = Field(
        default="password",
        description="Neo4j password"
    )
    neo4j_database: str = Field(
        default="neo4j",
        description="Neo4j database name"
    )

    # Workflow settings
    max_iterations: int = Field(
        default=50,
        description="Maximum workflow iterations"
    )
    default_timeout: int = Field(
        default=300,
        description="Default operation timeout in seconds"
    )

    # CORS settings
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:8000",
        description="Comma-separated list of allowed CORS origins"
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins string into list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Returns:
        Settings instance loaded from environment.
    """
    return Settings()
