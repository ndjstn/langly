"""
Unit tests for Pydantic schemas in app.core.schemas.

These tests verify actual validation behavior of the production
Pydantic models, including field constraints, enum validation,
default factory functions, and serialization.
"""
import pytest
from datetime import datetime
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.core.schemas import (
    Message,
    MessageRole,
    ToolCall,
    ToolResult,
    TaskType,
    TaskPriority,
    TaskStatus,
    AgentType,
    ScratchpadEntry,
    Task,
    AgentStateSchema,
    WorkflowStatus,
    WorkflowConfig,
    WorkflowRun,
    ChatRequest,
    ChatResponse,
    HealthStatus,
    AgentInfo,
    InterventionType,
    InterventionRequest,
    InterventionResponse,
)


class TestMessageRole:
    """Tests for MessageRole enum."""

    def test_valid_roles(self) -> None:
        """Test all valid message roles."""
        assert MessageRole.USER == "user"
        assert MessageRole.ASSISTANT == "assistant"
        assert MessageRole.SYSTEM == "system"
        assert MessageRole.TOOL == "tool"

    def test_role_values(self) -> None:
        """Test that roles are strings."""
        for role in MessageRole:
            assert isinstance(role.value, str)

    def test_role_count(self) -> None:
        """Test that we have expected number of roles."""
        assert len(MessageRole) == 4


class TestMessage:
    """Tests for Message model."""

    def test_message_creation_with_required_fields(self) -> None:
        """Test creating a message with required fields only."""
        msg = Message(role=MessageRole.USER, content="Hello")
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello"
        assert isinstance(msg.id, UUID)
        assert isinstance(msg.timestamp, datetime)
        assert msg.name is None
        assert msg.metadata == {}

    def test_message_with_all_fields(self) -> None:
        """Test creating a message with all fields."""
        msg_id = uuid4()
        ts = datetime(2024, 1, 1, 12, 0, 0)
        msg = Message(
            id=msg_id,
            role=MessageRole.TOOL,
            content="Tool result",
            name="read_file",
            timestamp=ts,
            metadata={"key": "value"},
        )
        assert msg.id == msg_id
        assert msg.role == MessageRole.TOOL
        assert msg.content == "Tool result"
        assert msg.name == "read_file"
        assert msg.timestamp == ts
        assert msg.metadata == {"key": "value"}

    def test_message_invalid_role(self) -> None:
        """Test that invalid role raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            Message(role="invalid_role", content="Test")
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "role" in str(errors[0]["loc"])

    def test_message_serialization(self) -> None:
        """Test message model_dump serialization."""
        msg = Message(role=MessageRole.USER, content="Test")
        data = msg.model_dump()
        assert "id" in data
        assert data["role"] == "user"
        assert data["content"] == "Test"
        assert "timestamp" in data
        assert data["metadata"] == {}


class TestToolCall:
    """Tests for ToolCall model."""

    def test_tool_call_creation(self) -> None:
        """Test creating a tool call."""
        tc = ToolCall(name="read_file", arguments={"path": "test.txt"})
        assert tc.name == "read_file"
        assert tc.arguments == {"path": "test.txt"}
        assert isinstance(tc.id, str)

    def test_tool_call_with_custom_id(self) -> None:
        """Test tool call with custom ID."""
        tc = ToolCall(id="custom-id", name="write_file", arguments={})
        assert tc.id == "custom-id"

    def test_tool_call_default_arguments(self) -> None:
        """Test tool call with default empty arguments."""
        tc = ToolCall(name="list_files")
        assert tc.arguments == {}


class TestToolResult:
    """Tests for ToolResult model."""

    def test_tool_result_success(self) -> None:
        """Test successful tool result."""
        result = ToolResult(
            tool_call_id="tc-123",
            result={"content": "file contents"},
            success=True,
        )
        assert result.tool_call_id == "tc-123"
        assert result.result == {"content": "file contents"}
        assert result.error is None
        assert result.success is True

    def test_tool_result_failure(self) -> None:
        """Test failed tool result."""
        result = ToolResult(
            tool_call_id="tc-456",
            error="File not found",
            success=False,
        )
        assert result.tool_call_id == "tc-456"
        assert result.result is None
        assert result.error == "File not found"
        assert result.success is False


class TestTaskEnums:
    """Tests for task-related enums."""

    def test_task_type_values(self) -> None:
        """Test TaskType enum values."""
        assert TaskType.CODE == "code"
        assert TaskType.ARCHITECTURE == "architecture"
        assert TaskType.TEST == "test"
        assert TaskType.REVIEW == "review"
        assert TaskType.DOCUMENTATION == "documentation"
        assert TaskType.GENERAL == "general"
        assert TaskType.PLANNING == "planning"
        assert len(TaskType) == 7

    def test_task_priority_values(self) -> None:
        """Test TaskPriority enum values."""
        assert TaskPriority.LOW == "low"
        assert TaskPriority.MEDIUM == "medium"
        assert TaskPriority.HIGH == "high"
        assert TaskPriority.CRITICAL == "critical"
        assert len(TaskPriority) == 4

    def test_task_status_values(self) -> None:
        """Test TaskStatus enum values."""
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.IN_PROGRESS == "in_progress"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.FAILED == "failed"
        assert TaskStatus.NEEDS_REVIEW == "needs_review"
        assert TaskStatus.BLOCKED == "blocked"
        assert len(TaskStatus) == 6


class TestAgentType:
    """Tests for AgentType enum."""

    def test_agent_type_values(self) -> None:
        """Test all agent type values."""
        assert AgentType.PM == "pm"
        assert AgentType.CODER == "coder"
        assert AgentType.ARCHITECT == "architect"
        assert AgentType.TESTER == "tester"
        assert AgentType.REVIEWER == "reviewer"
        assert AgentType.DOCS == "docs"
        assert AgentType.ROUTER == "router"
        assert AgentType.GUARDIAN == "guardian"
        assert len(AgentType) == 8


class TestScratchpadEntry:
    """Tests for ScratchpadEntry model."""

    def test_scratchpad_entry_creation(self) -> None:
        """Test creating a scratchpad entry."""
        entry = ScratchpadEntry(key="analysis", value={"result": "good"})
        assert entry.key == "analysis"
        assert entry.value == {"result": "good"}
        assert isinstance(entry.timestamp, datetime)
        assert entry.agent_type is None

    def test_scratchpad_entry_with_agent(self) -> None:
        """Test scratchpad entry with agent type."""
        entry = ScratchpadEntry(
            key="code_draft",
            value="def foo(): pass",
            agent_type=AgentType.CODER,
        )
        assert entry.agent_type == AgentType.CODER


class TestTask:
    """Tests for Task model."""

    def test_task_creation_minimal(self) -> None:
        """Test creating a task with minimal fields."""
        task = Task(content="Implement feature X")
        assert isinstance(task.id, UUID)
        assert task.content == "Implement feature X"
        assert task.status == TaskStatus.PENDING
        assert task.assigned_to is None
        assert task.parent_id is None
        assert isinstance(task.created_at, datetime)
        assert task.completed_at is None
        assert task.result is None
        assert task.error is None

    def test_task_creation_full(self) -> None:
        """Test creating a task with all fields."""
        task_id = uuid4()
        parent_id = uuid4()
        created = datetime(2024, 1, 1)
        completed = datetime(2024, 1, 2)

        task = Task(
            id=task_id,
            content="Write tests",
            status=TaskStatus.COMPLETED,
            assigned_to=AgentType.TESTER,
            parent_id=parent_id,
            created_at=created,
            completed_at=completed,
            result="All tests passed",
            error=None,
        )

        assert task.id == task_id
        assert task.content == "Write tests"
        assert task.status == TaskStatus.COMPLETED
        assert task.assigned_to == AgentType.TESTER
        assert task.parent_id == parent_id
        assert task.created_at == created
        assert task.completed_at == completed
        assert task.result == "All tests passed"


class TestAgentStateSchema:
    """Tests for AgentStateSchema model."""

    def test_agent_state_defaults(self) -> None:
        """Test AgentStateSchema with default values."""
        state = AgentStateSchema()
        assert isinstance(state.session_id, UUID)
        assert state.messages == []
        assert state.current_agent is None
        assert state.task_status == TaskStatus.PENDING
        assert state.scratchpad == {}
        assert state.pending_tasks == []
        assert state.completed_tasks == []
        assert state.iteration_count == 0
        assert state.error is None
        assert state.needs_human_input is False
        assert state.human_input_request is None

    def test_agent_state_with_messages(self) -> None:
        """Test AgentStateSchema with messages."""
        msg = Message(role=MessageRole.USER, content="Hello")
        state = AgentStateSchema(messages=[msg])
        assert len(state.messages) == 1
        assert state.messages[0].content == "Hello"

    def test_agent_state_with_tasks(self) -> None:
        """Test AgentStateSchema with pending and completed tasks."""
        pending = Task(content="Task 1", status=TaskStatus.PENDING)
        completed = Task(content="Task 2", status=TaskStatus.COMPLETED)

        state = AgentStateSchema(
            pending_tasks=[pending],
            completed_tasks=[completed],
        )
        assert len(state.pending_tasks) == 1
        assert len(state.completed_tasks) == 1


class TestWorkflowModels:
    """Tests for workflow-related models."""

    def test_workflow_status_values(self) -> None:
        """Test WorkflowStatus enum values."""
        assert WorkflowStatus.CREATED == "created"
        assert WorkflowStatus.RUNNING == "running"
        assert WorkflowStatus.PAUSED == "paused"
        assert WorkflowStatus.WAITING_FOR_HUMAN == "waiting_for_human"
        assert WorkflowStatus.COMPLETED == "completed"
        assert WorkflowStatus.FAILED == "failed"
        assert WorkflowStatus.CANCELLED == "cancelled"
        assert len(WorkflowStatus) == 7

    def test_workflow_config_defaults(self) -> None:
        """Test WorkflowConfig default values."""
        config = WorkflowConfig()
        assert isinstance(config.id, UUID)
        assert config.max_iterations == 50
        assert config.timeout_seconds == 300
        assert config.enable_human_in_loop is True
        assert config.enable_checkpointing is True
        assert config.parallel_execution is False

    def test_workflow_config_validation(self) -> None:
        """Test WorkflowConfig field constraints."""
        # Test min constraint on max_iterations
        with pytest.raises(ValidationError):
            WorkflowConfig(max_iterations=0)

        # Test max constraint on max_iterations
        with pytest.raises(ValidationError):
            WorkflowConfig(max_iterations=501)

        # Test min constraint on timeout_seconds
        with pytest.raises(ValidationError):
            WorkflowConfig(timeout_seconds=5)

        # Test max constraint on timeout_seconds
        with pytest.raises(ValidationError):
            WorkflowConfig(timeout_seconds=4000)

    def test_workflow_run_defaults(self) -> None:
        """Test WorkflowRun default values."""
        run = WorkflowRun()
        assert isinstance(run.id, UUID)
        assert run.config_id is None
        assert run.status == WorkflowStatus.CREATED
        assert run.current_node is None
        assert run.thread_id is None
        assert isinstance(run.created_at, datetime)
        assert isinstance(run.updated_at, datetime)
        assert run.completed_at is None
        assert run.error is None
        assert run.result is None


class TestAPIModels:
    """Tests for API request/response models."""

    def test_chat_request_valid(self) -> None:
        """Test valid ChatRequest."""
        request = ChatRequest(message="Hello, world!")
        assert request.message == "Hello, world!"
        assert request.session_id is None

    def test_chat_request_with_session(self) -> None:
        """Test ChatRequest with existing session."""
        session_id = uuid4()
        request = ChatRequest(message="Continue", session_id=session_id)
        assert request.session_id == session_id

    def test_chat_request_empty_message(self) -> None:
        """Test that empty message is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ChatRequest(message="")
        errors = exc_info.value.errors()
        assert any("message" in str(e["loc"]) for e in errors)

    def test_chat_response(self) -> None:
        """Test ChatResponse creation."""
        session_id = uuid4()
        response = ChatResponse(
            session_id=session_id,
            message="Hello!",
            agent_type=AgentType.PM,
            status=WorkflowStatus.RUNNING,
        )
        assert response.session_id == session_id
        assert response.message == "Hello!"
        assert response.agent_type == AgentType.PM
        assert response.status == WorkflowStatus.RUNNING
        assert response.tasks == []

    def test_health_status_defaults(self) -> None:
        """Test HealthStatus default values."""
        health = HealthStatus()
        assert health.status == "healthy"
        assert health.ollama == "unknown"
        assert health.neo4j == "unknown"
        assert health.version == "0.1.0"
        assert isinstance(health.timestamp, datetime)

    def test_agent_info(self) -> None:
        """Test AgentInfo creation."""
        info = AgentInfo(
            agent_type=AgentType.CODER,
            name="Coder Agent",
            description="Writes code",
            model="granite-code:8b",
        )
        assert info.agent_type == AgentType.CODER
        assert info.name == "Coder Agent"
        assert info.description == "Writes code"
        assert info.model == "granite-code:8b"
        assert info.status == "ready"


class TestInterventionModels:
    """Tests for intervention-related models."""

    def test_intervention_type_values(self) -> None:
        """Test InterventionType enum values."""
        assert InterventionType.APPROVAL == "approval"
        assert InterventionType.CLARIFICATION == "clarification"
        assert InterventionType.OVERRIDE == "override"
        assert InterventionType.REDIRECT == "redirect"
        assert len(InterventionType) == 4

    def test_intervention_request(self) -> None:
        """Test InterventionRequest creation."""
        workflow_id = uuid4()
        request = InterventionRequest(
            workflow_id=workflow_id,
            intervention_type=InterventionType.APPROVAL,
            prompt="Approve deployment?",
            options=["Yes", "No"],
        )
        assert isinstance(request.id, UUID)
        assert request.workflow_id == workflow_id
        assert request.intervention_type == InterventionType.APPROVAL
        assert request.prompt == "Approve deployment?"
        assert request.options == ["Yes", "No"]
        assert request.context == {}
        assert isinstance(request.created_at, datetime)
        assert request.timeout_seconds == 300

    def test_intervention_request_timeout_constraints(self) -> None:
        """Test InterventionRequest timeout constraints."""
        workflow_id = uuid4()

        # Test min constraint
        with pytest.raises(ValidationError):
            InterventionRequest(
                workflow_id=workflow_id,
                intervention_type=InterventionType.APPROVAL,
                prompt="Test",
                timeout_seconds=5,
            )

        # Test max constraint
        with pytest.raises(ValidationError):
            InterventionRequest(
                workflow_id=workflow_id,
                intervention_type=InterventionType.APPROVAL,
                prompt="Test",
                timeout_seconds=4000,
            )

    def test_intervention_response(self) -> None:
        """Test InterventionResponse creation."""
        request_id = uuid4()
        response = InterventionResponse(
            request_id=request_id,
            response="Yes",
            selected_option="Yes",
            notes="Looks good",
        )
        assert response.request_id == request_id
        assert response.response == "Yes"
        assert response.selected_option == "Yes"
        assert response.notes == "Looks good"
        assert isinstance(response.responded_at, datetime)


class TestModelSerialization:
    """Tests for model serialization and JSON schema generation."""

    def test_message_json_schema(self) -> None:
        """Test Message generates valid JSON schema."""
        schema = Message.model_json_schema()
        assert "properties" in schema
        assert "role" in schema["properties"]
        assert "content" in schema["properties"]

    def test_task_json_schema(self) -> None:
        """Test Task generates valid JSON schema."""
        schema = Task.model_json_schema()
        assert "properties" in schema
        assert "content" in schema["properties"]
        assert "status" in schema["properties"]

    def test_workflow_config_json_schema(self) -> None:
        """Test WorkflowConfig generates valid JSON schema."""
        schema = WorkflowConfig.model_json_schema()
        assert "properties" in schema
        assert "max_iterations" in schema["properties"]

    def test_model_round_trip(self) -> None:
        """Test model serialization and deserialization round trip."""
        original = Task(
            content="Test task",
            status=TaskStatus.IN_PROGRESS,
            assigned_to=AgentType.CODER,
        )

        # Serialize to dict
        data = original.model_dump(mode="json")

        # Deserialize back
        restored = Task.model_validate(data)

        assert restored.content == original.content
        assert restored.status == original.status
        assert restored.assigned_to == original.assigned_to


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_message_with_empty_content(self) -> None:
        """Test message with empty string content."""
        msg = Message(role=MessageRole.USER, content="")
        assert msg.content == ""

    def test_task_with_complex_result(self) -> None:
        """Test task with complex nested result."""
        complex_result = {
            "files": ["a.py", "b.py"],
            "metrics": {"lines": 100, "coverage": 0.85},
            "nested": {"deep": {"value": True}},
        }
        task = Task(
            content="Complex task",
            status=TaskStatus.COMPLETED,
            result=complex_result,
        )
        assert task.result == complex_result

    def test_agent_state_with_large_scratchpad(self) -> None:
        """Test AgentStateSchema with large scratchpad."""
        scratchpad = {
            f"key_{i}": ScratchpadEntry(key=f"key_{i}", value=f"value_{i}")
            for i in range(100)
        }
        state = AgentStateSchema(scratchpad=scratchpad)
        assert len(state.scratchpad) == 100

    def test_workflow_config_edge_values(self) -> None:
        """Test WorkflowConfig with edge constraint values."""
        # Test minimum valid values
        config_min = WorkflowConfig(
            max_iterations=1,
            timeout_seconds=10,
        )
        assert config_min.max_iterations == 1
        assert config_min.timeout_seconds == 10

        # Test maximum valid values
        config_max = WorkflowConfig(
            max_iterations=500,
            timeout_seconds=3600,
        )
        assert config_max.max_iterations == 500
        assert config_max.timeout_seconds == 3600
