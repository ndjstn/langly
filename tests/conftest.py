# =============================================================================
# Pytest Configuration and Fixtures
# =============================================================================
"""
Pytest configuration and shared fixtures for Langly test suite.

This module provides:
- Shared fixtures for all test modules
- Mock objects for external dependencies (Ollama, Neo4j)
- Test client configuration for FastAPI
- Async test utilities
"""
from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator, Generator
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

if TYPE_CHECKING:
    from httpx import AsyncClient


# =============================================================================
# Environment Setup
# =============================================================================

# Set test environment variables before importing app modules
os.environ.setdefault("LANGLY_ENV", "test")
os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
os.environ.setdefault("NEO4J_USER", "neo4j")
os.environ.setdefault("NEO4J_PASSWORD", "test_password")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ.setdefault("LOG_LEVEL", "DEBUG")


# =============================================================================
# Pytest Plugins and Configuration
# =============================================================================

pytest_plugins = [
    "pytest_asyncio",
]


def pytest_configure(config: pytest.Config) -> None:
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as unit test (fast, no external deps)"
    )
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test (may need services)",
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test (full system)"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "requires_ollama: mark test as requiring Ollama"
    )
    config.addinivalue_line(
        "markers", "requires_neo4j: mark test as requiring Neo4j"
    )
    config.addinivalue_line(
        "markers", "user: mark test as user flow test"
    )


# =============================================================================
# Event Loop Configuration
# =============================================================================

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# Application Fixtures
# =============================================================================

@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.app_name = "Langly Test"
    settings.app_version = "0.1.0-test"
    settings.debug = True
    settings.log_level = "DEBUG"
    settings.neo4j_uri = "bolt://localhost:7687"
    settings.neo4j_user = "neo4j"
    settings.neo4j_password = "test_password"
    settings.ollama_base_url = "http://localhost:11434"
    settings.default_model = "granite3.1-dense:2b"
    settings.embedding_model = "granite-embedding:278m"
    settings.guardian_model = "granite3.1-dense:2b"
    settings.router_model = "granite3.1-moe:1b"
    settings.request_timeout = 30.0
    settings.max_retries = 3
    settings.circuit_breaker_threshold = 5
    settings.circuit_breaker_timeout = 60.0
    return settings


@pytest.fixture
def app() -> Generator[Any, None, None]:
    """Create FastAPI application for testing."""
    # Import here to avoid circular imports
    from app.main import app as fastapi_app

    yield fastapi_app


@pytest.fixture
def client(app: Any) -> Generator[TestClient, None, None]:
    """Create test client for FastAPI application."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
async def async_client(
    app: Any,
) -> AsyncGenerator["AsyncClient", None]:
    """Create async test client for FastAPI application."""
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


# =============================================================================
# Mock External Services
# =============================================================================

@pytest.fixture
def mock_ollama_client() -> MagicMock:
    """Create mock Ollama client."""
    client = MagicMock()

    # Mock chat completion
    client.chat = AsyncMock(
        return_value={
            "message": {
                "role": "assistant",
                "content": "Mock response from Granite model",
            },
            "done": True,
            "total_duration": 1000000000,
            "load_duration": 500000000,
            "prompt_eval_count": 10,
            "eval_count": 20,
        }
    )

    # Mock embeddings
    client.embeddings = AsyncMock(
        return_value={
            "embedding": [0.1] * 768,
        }
    )

    # Mock list models
    client.list = AsyncMock(
        return_value={
            "models": [
                {"name": "granite3.1-dense:2b", "size": 2000000000},
                {"name": "granite3.1-dense:8b", "size": 8000000000},
                {"name": "granite-embedding:278m", "size": 278000000},
            ]
        }
    )

    return client


@pytest.fixture
def mock_neo4j_driver() -> MagicMock:
    """Create mock Neo4j driver."""
    driver = MagicMock()
    session = MagicMock()
    tx = MagicMock()

    # Mock transaction results
    tx.run = MagicMock(return_value=MagicMock(data=lambda: []))
    session.run = MagicMock(return_value=MagicMock(data=lambda: []))
    session.begin_transaction = MagicMock(return_value=tx)
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)

    # Async context manager support
    async_session = AsyncMock()
    async_session.run = AsyncMock(
        return_value=MagicMock(data=lambda: [])
    )
    async_session.__aenter__ = AsyncMock(return_value=async_session)
    async_session.__aexit__ = AsyncMock(return_value=False)

    driver.session = MagicMock(return_value=async_session)
    driver.close = AsyncMock()

    return driver


@pytest.fixture
def mock_memory_manager(mock_neo4j_driver: MagicMock) -> MagicMock:
    """Create mock memory manager."""
    manager = MagicMock()
    manager.driver = mock_neo4j_driver

    manager.store_message = AsyncMock(return_value="msg-123")
    manager.get_messages = AsyncMock(return_value=[])
    manager.store_task = AsyncMock(return_value="task-123")
    manager.get_task = AsyncMock(return_value=None)
    manager.update_task_status = AsyncMock()
    manager.store_error = AsyncMock()
    manager.store_knowledge = AsyncMock()
    manager.search_knowledge = AsyncMock(return_value=[])
    manager.get_agent_context = AsyncMock(return_value={})
    manager.close = AsyncMock()

    return manager


# =============================================================================
# Agent Fixtures
# =============================================================================

@pytest.fixture
def mock_agent_state() -> dict[str, Any]:
    """Create mock agent state for testing."""
    return {
        "session_id": "test-session-123",
        "messages": [],
        "current_agent": "project_manager",
        "task_queue": [],
        "completed_tasks": [],
        "errors": [],
        "metadata": {
            "created_at": "2025-01-01T00:00:00Z",
            "last_updated": "2025-01-01T00:00:00Z",
        },
        "intervention_required": False,
        "intervention_reason": None,
    }


@pytest.fixture
def sample_task() -> dict[str, Any]:
    """Create sample task for testing."""
    return {
        "id": "task-123",
        "type": "code_generation",
        "description": "Create a Python function to calculate factorial",
        "priority": "high",
        "assigned_agent": "coder",
        "status": "pending",
        "metadata": {},
    }


@pytest.fixture
def sample_message() -> dict[str, Any]:
    """Create sample message for testing."""
    return {
        "role": "user",
        "content": "Create a simple REST API with FastAPI",
        "timestamp": "2025-01-01T00:00:00Z",
    }


# =============================================================================
# Tool Fixtures
# =============================================================================

@pytest.fixture
def mock_tool_registry() -> MagicMock:
    """Create mock tool registry."""
    registry = MagicMock()

    registry.get_tool = MagicMock(return_value=None)
    registry.list_tools = MagicMock(return_value=[])
    registry.register_tool = MagicMock()
    registry.unregister_tool = MagicMock()
    registry.execute_tool = AsyncMock(
        return_value={"success": True, "result": "Mock result"}
    )

    return registry


@pytest.fixture
def sample_tool_definition() -> dict[str, Any]:
    """Create sample tool definition for testing."""
    return {
        "name": "test_tool",
        "description": "A test tool for unit testing",
        "parameters": {
            "type": "object",
            "properties": {
                "input": {
                    "type": "string",
                    "description": "Input parameter",
                },
            },
            "required": ["input"],
        },
    }


# =============================================================================
# Workflow Fixtures
# =============================================================================

@pytest.fixture
def sample_workflow_config() -> dict[str, Any]:
    """Create sample workflow configuration."""
    return {
        "name": "test_workflow",
        "description": "Test workflow for unit testing",
        "nodes": [
            {
                "id": "start",
                "type": "entry",
                "next": "process",
            },
            {
                "id": "process",
                "type": "agent",
                "agent": "coder",
                "next": "end",
            },
            {
                "id": "end",
                "type": "exit",
            },
        ],
        "edges": [
            {"from": "start", "to": "process"},
            {"from": "process", "to": "end"},
        ],
    }


# =============================================================================
# Cleanup Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def cleanup_after_test() -> Generator[None, None, None]:
    """Clean up after each test."""
    yield
    # Cleanup code runs after each test
    # Add any necessary cleanup here


@pytest.fixture
def temp_file(tmp_path: Any) -> Generator[Any, None, None]:
    """Create temporary file for testing."""
    file_path = tmp_path / "test_file.txt"
    file_path.write_text("test content")
    yield file_path
    # Cleanup is automatic with tmp_path


# =============================================================================
# Patch Fixtures
# =============================================================================

@pytest.fixture
def patch_ollama(mock_ollama_client: MagicMock) -> Generator[None, None, None]:
    """Patch Ollama client for testing."""
    with patch(
        "app.llm.ollama_client.AsyncClient",
        return_value=mock_ollama_client,
    ):
        yield


@pytest.fixture
def patch_neo4j(mock_neo4j_driver: MagicMock) -> Generator[None, None, None]:
    """Patch Neo4j driver for testing."""
    with patch(
        "neo4j.AsyncGraphDatabase.driver",
        return_value=mock_neo4j_driver,
    ):
        yield


@pytest.fixture
def patch_all_external(
    patch_ollama: None,
    patch_neo4j: None,
) -> Generator[None, None, None]:
    """Patch all external services for unit testing."""
    yield


# =============================================================================
# Hypothesis Strategies (for property-based testing)
# =============================================================================

try:
    from hypothesis import strategies as st

    @pytest.fixture
    def valid_task_description() -> st.SearchStrategy[str]:
        """Generate valid task descriptions."""
        return st.text(
            min_size=10,
            max_size=1000,
            alphabet=st.characters(
                whitelist_categories=("L", "N", "P", "Z"),
            ),
        )

    @pytest.fixture
    def valid_agent_name() -> st.SearchStrategy[str]:
        """Generate valid agent names."""
        return st.sampled_from([
            "project_manager",
            "coder",
            "reviewer",
            "tester",
            "architect",
            "documenter",
        ])

except ImportError:
    # Hypothesis not installed, skip these fixtures
    pass
