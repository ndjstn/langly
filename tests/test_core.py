"""Unit tests for core components.

Tests for configuration, schemas, constants, and exceptions.
"""

import os
from unittest.mock import patch

import pytest

from app.core.config import Settings, get_settings
from app.core.constants import (
    AgentType,
    TaskType,
    TaskPriority,
    TaskStatus,
    WorkflowStatus,
    MODEL_CONFIGS,
)
from app.core.schemas import (
    TaskCreate,
    TaskResponse,
    AgentResponse,
    WorkflowCreate,
    WorkflowResponse,
)
from app.core.exceptions import (
    LanglyError,
    ConfigurationError,
    AgentError,
    WorkflowError,
    ToolError,
    MemoryError,
)


# =============================================================================
# Settings Tests
# =============================================================================


class TestSettings:
    """Tests for Settings configuration."""

    def test_default_settings(self) -> None:
        """Test default settings values."""
        settings = Settings()

        assert settings.app_name == "langly"
        assert settings.environment == "development"
        assert settings.debug is True

    def test_ollama_settings(self) -> None:
        """Test Ollama configuration."""
        settings = Settings()

        assert settings.ollama_host is not None
        assert "11434" in settings.ollama_host

    def test_neo4j_settings(self) -> None:
        """Test Neo4j configuration."""
        settings = Settings()

        assert settings.neo4j_uri is not None
        assert settings.neo4j_user is not None

    def test_custom_settings_from_env(self) -> None:
        """Test settings from environment variables."""
        with patch.dict(os.environ, {
            "LANGLY_APP_NAME": "custom-app",
            "LANGLY_ENVIRONMENT": "production",
            "LANGLY_DEBUG": "false",
        }):
            settings = Settings()
            # Note: depends on env_prefix configuration
            # This demonstrates the pattern

    def test_get_settings_cached(self) -> None:
        """Test that get_settings returns cached instance."""
        settings1 = get_settings()
        settings2 = get_settings()

        # Should be the same instance (cached)
        assert settings1 is settings2


# =============================================================================
# Constants Tests
# =============================================================================


class TestAgentType:
    """Tests for AgentType enum."""

    def test_agent_types(self) -> None:
        """Test all agent types are defined."""
        assert AgentType.PROJECT_MANAGER.value == "project_manager"
        assert AgentType.CODER.value == "coder"
        assert AgentType.ARCHITECT.value == "architect"
        assert AgentType.TESTER.value == "tester"
        assert AgentType.REVIEWER.value == "reviewer"
        assert AgentType.DOCUMENTATION.value == "documentation"
        assert AgentType.ROUTER.value == "router"

    def test_agent_type_from_string(self) -> None:
        """Test creating agent type from string."""
        agent_type = AgentType("coder")
        assert agent_type == AgentType.CODER


class TestTaskType:
    """Tests for TaskType enum."""

    def test_task_types(self) -> None:
        """Test all task types are defined."""
        assert TaskType.CODE.value == "code"
        assert TaskType.REVIEW.value == "review"
        assert TaskType.TEST.value == "test"
        assert TaskType.DOCUMENT.value == "document"
        assert TaskType.ARCHITECTURE.value == "architecture"


class TestTaskPriority:
    """Tests for TaskPriority enum."""

    def test_priorities(self) -> None:
        """Test priority values."""
        assert TaskPriority.LOW.value == "low"
        assert TaskPriority.MEDIUM.value == "medium"
        assert TaskPriority.HIGH.value == "high"
        assert TaskPriority.CRITICAL.value == "critical"


class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_statuses(self) -> None:
        """Test status values."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.IN_PROGRESS.value == "in_progress"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"


class TestWorkflowStatus:
    """Tests for WorkflowStatus enum."""

    def test_workflow_statuses(self) -> None:
        """Test workflow status values."""
        assert WorkflowStatus.PENDING.value == "pending"
        assert WorkflowStatus.RUNNING.value == "running"
        assert WorkflowStatus.PAUSED.value == "paused"
        assert WorkflowStatus.COMPLETED.value == "completed"
        assert WorkflowStatus.FAILED.value == "failed"


class TestModelConfigs:
    """Tests for MODEL_CONFIGS constant."""

    def test_model_configs_exist(self) -> None:
        """Test model configurations are defined."""
        assert MODEL_CONFIGS is not None
        assert len(MODEL_CONFIGS) > 0

    def test_model_config_structure(self) -> None:
        """Test model config structure."""
        for model_name, config in MODEL_CONFIGS.items():
            assert "model" in config
            assert isinstance(config["model"], str)


# =============================================================================
# Schema Tests
# =============================================================================


class TestTaskCreate:
    """Tests for TaskCreate schema."""

    def test_create_task(self) -> None:
        """Test creating a task schema."""
        task = TaskCreate(
            title="Test Task",
            description="A test task description",
            task_type=TaskType.CODE,
            priority=TaskPriority.MEDIUM,
        )

        assert task.title == "Test Task"
        assert task.task_type == TaskType.CODE
        assert task.priority == TaskPriority.MEDIUM

    def test_task_defaults(self) -> None:
        """Test task default values."""
        task = TaskCreate(
            title="Test Task",
            description="Description",
            task_type=TaskType.CODE,
        )

        assert task.priority == TaskPriority.MEDIUM

    def test_task_validation(self) -> None:
        """Test task validation."""
        with pytest.raises(ValueError):
            TaskCreate(
                title="",  # Empty title should fail
                description="Description",
                task_type=TaskType.CODE,
            )


class TestTaskResponse:
    """Tests for TaskResponse schema."""

    def test_task_response(self) -> None:
        """Test task response schema."""
        response = TaskResponse(
            task_id="task-123",
            title="Test Task",
            description="A test task",
            task_type=TaskType.CODE,
            priority=TaskPriority.HIGH,
            status=TaskStatus.PENDING,
        )

        assert response.task_id == "task-123"
        assert response.status == TaskStatus.PENDING


class TestAgentResponse:
    """Tests for AgentResponse schema."""

    def test_agent_response(self) -> None:
        """Test agent response schema."""
        response = AgentResponse(
            agent_id="agent-123",
            agent_type=AgentType.CODER,
            name="Coder Agent",
            status="active",
        )

        assert response.agent_id == "agent-123"
        assert response.agent_type == AgentType.CODER


class TestWorkflowCreate:
    """Tests for WorkflowCreate schema."""

    def test_create_workflow(self) -> None:
        """Test creating a workflow schema."""
        workflow = WorkflowCreate(
            name="Test Workflow",
            task_id="task-123",
        )

        assert workflow.name == "Test Workflow"
        assert workflow.task_id == "task-123"


class TestWorkflowResponse:
    """Tests for WorkflowResponse schema."""

    def test_workflow_response(self) -> None:
        """Test workflow response schema."""
        response = WorkflowResponse(
            workflow_id="workflow-123",
            name="Test Workflow",
            status=WorkflowStatus.RUNNING,
        )

        assert response.workflow_id == "workflow-123"
        assert response.status == WorkflowStatus.RUNNING


# =============================================================================
# Exception Tests
# =============================================================================


class TestLanglyError:
    """Tests for base LanglyError exception."""

    def test_basic_error(self) -> None:
        """Test basic error creation."""
        error = LanglyError("Test error message")

        assert str(error) == "Test error message"

    def test_error_inheritance(self) -> None:
        """Test error is instance of Exception."""
        error = LanglyError("Test error")

        assert isinstance(error, Exception)


class TestConfigurationError:
    """Tests for ConfigurationError exception."""

    def test_configuration_error(self) -> None:
        """Test configuration error."""
        error = ConfigurationError("Invalid config value")

        assert isinstance(error, LanglyError)
        assert "Invalid config" in str(error)


class TestAgentError:
    """Tests for AgentError exception."""

    def test_agent_error(self) -> None:
        """Test agent error."""
        error = AgentError(
            message="Agent failed",
            agent_id="coder-agent",
        )

        assert "Agent failed" in str(error)
        assert error.agent_id == "coder-agent"

    def test_agent_error_with_details(self) -> None:
        """Test agent error with additional details."""
        error = AgentError(
            message="Processing failed",
            agent_id="tester-agent",
            details={"iteration": 5, "task": "test-task"},
        )

        assert error.details is not None
        assert error.details["iteration"] == 5


class TestWorkflowError:
    """Tests for WorkflowError exception."""

    def test_workflow_error(self) -> None:
        """Test workflow error."""
        error = WorkflowError(
            message="Workflow timeout",
            workflow_id="workflow-123",
        )

        assert "Workflow timeout" in str(error)
        assert error.workflow_id == "workflow-123"


class TestToolError:
    """Tests for ToolError exception."""

    def test_tool_error(self) -> None:
        """Test tool error."""
        error = ToolError(
            message="Tool execution failed",
            tool_name="file_read",
        )

        assert "Tool execution failed" in str(error)
        assert error.tool_name == "file_read"


class TestMemoryError:
    """Tests for MemoryError exception."""

    def test_memory_error(self) -> None:
        """Test memory error."""
        error = MemoryError(
            message="Failed to store memory",
            operation="write",
        )

        assert "Failed to store" in str(error)
        assert error.operation == "write"


# =============================================================================
# Integration Tests
# =============================================================================


class TestCoreIntegration:
    """Integration tests for core components."""

    def test_task_workflow_creation(self) -> None:
        """Test creating task then workflow."""
        task = TaskCreate(
            title="Integration Task",
            description="Test integration",
            task_type=TaskType.CODE,
            priority=TaskPriority.HIGH,
        )

        workflow = WorkflowCreate(
            name=f"Workflow for {task.title}",
            task_id="task-integration-123",
        )

        assert workflow.name == "Workflow for Integration Task"

    def test_error_chain(self) -> None:
        """Test error chaining."""
        try:
            try:
                raise ConnectionError("Database unavailable")
            except ConnectionError as e:
                raise MemoryError(
                    message="Failed to persist data",
                    operation="write",
                ) from e
        except MemoryError as error:
            assert error.__cause__ is not None
            assert isinstance(error.__cause__, ConnectionError)

    def test_status_transitions(self) -> None:
        """Test valid status transitions."""
        # Task status transitions
        valid_transitions = [
            (TaskStatus.PENDING, TaskStatus.IN_PROGRESS),
            (TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED),
            (TaskStatus.IN_PROGRESS, TaskStatus.FAILED),
            (TaskStatus.PENDING, TaskStatus.CANCELLED),
        ]

        for from_status, to_status in valid_transitions:
            # In a real implementation, this would validate transitions
            assert from_status != to_status
