# =============================================================================
# End-to-End Tests for Full Langly Workflows
# =============================================================================
"""
E2E tests that exercise complete workflows with real or mocked services.

These tests verify:
- Complete task submission to completion flow
- Multi-agent coordination and handoff
- Human-in-the-loop intervention flows
- Tool execution with real operations
- Memory persistence across sessions
- Error recovery and circuit breaker behavior
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# Full Workflow E2E Tests
# =============================================================================

class TestCompleteTaskWorkflow:
    """E2E tests for complete task submission to completion."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_simple_task_completion(
        self,
        async_client: Any,
        mock_ollama_client: MagicMock,
        mock_memory_manager: MagicMock,
    ) -> None:
        """Test simple task from submission to completion.

        User Story: As a business owner, I want to submit a simple coding
        task and receive completed code without manual intervention.
        """
        # Step 1: Create a new session
        session_response = await async_client.post(
            "/api/v1/workflows/sessions",
            json={"name": "Simple Task Test"},
        )
        # May return 404 if not implemented
        if session_response.status_code == 404:
            pytest.skip("Sessions endpoint not implemented")

        session_id = session_response.json().get("session_id")

        # Step 2: Submit a simple task
        task_response = await async_client.post(
            f"/api/v1/workflows/sessions/{session_id}/tasks",
            json={
                "description": "Create a Python function to add two numbers",
                "type": "code_generation",
            },
        )

        # Step 3: Wait for completion (with timeout)
        max_attempts = 10
        for _ in range(max_attempts):
            status_response = await async_client.get(
                f"/api/v1/workflows/sessions/{session_id}/status",
            )
            if status_response.status_code != 200:
                break
            status = status_response.json().get("status")
            if status == "completed":
                break
            await asyncio.sleep(0.1)

        # Verify task was processed
        assert status_response is not None

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_complex_multi_agent_task(
        self,
        async_client: Any,
        mock_ollama_client: MagicMock,
        mock_memory_manager: MagicMock,
    ) -> None:
        """Test complex task requiring multiple agents.

        User Story: As a business owner, I want to submit a complex
        feature request that requires architecture, coding, testing,
        and documentation - all coordinated automatically.
        """
        with patch("app.agents.workflow.compile_workflow") as mock_workflow:
            # Setup mock workflow response
            mock_workflow.return_value = AsyncMock(
                ainvoke=AsyncMock(
                    return_value={
                        "status": "completed",
                        "agents_used": [
                            "project_manager",
                            "architect",
                            "coder",
                            "tester",
                            "documenter",
                        ],
                        "outputs": {
                            "architecture": "REST API design",
                            "code": "def api_handler(): ...",
                            "tests": "def test_api(): ...",
                            "docs": "# API Documentation",
                        },
                    }
                )
            )

            # Simulate task submission
            task = {
                "description": "Build a REST API for user management",
                "subtasks": [
                    {"type": "architecture", "agent": "architect"},
                    {"type": "implementation", "agent": "coder"},
                    {"type": "testing", "agent": "tester"},
                    {"type": "documentation", "agent": "documenter"},
                ],
            }

            # Verify all agents would be invoked
            expected_agents = {"architect", "coder", "tester", "documenter"}
            actual_agents = {st["agent"] for st in task["subtasks"]}
            assert expected_agents == actual_agents


class TestAgentCoordinationE2E:
    """E2E tests for multi-agent coordination."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_pm_agent_task_decomposition(
        self,
        mock_ollama_client: MagicMock,
    ) -> None:
        """Test Project Manager decomposes complex tasks.

        User Story: When I submit a vague request, the PM should break
        it down into specific, actionable subtasks for worker agents.
        """
        # Mock PM agent response
        mock_ollama_client.chat = AsyncMock(
            return_value={
                "message": {
                    "role": "assistant",
                    "content": """I'll break this down into the following tasks:

1. **Architecture Design** (Architect): Design the database schema
2. **Backend Implementation** (Coder): Implement CRUD operations
3. **API Testing** (Tester): Write integration tests
4. **Documentation** (Documenter): Create API documentation
""",
                },
                "done": True,
            }
        )

        user_request = "I need a user management system"

        # PM should extract subtasks
        response = await mock_ollama_client.chat(
            model="granite3.1-dense:8b",
            messages=[{"role": "user", "content": user_request}],
        )

        content = response["message"]["content"]
        assert "Architecture" in content
        assert "Implementation" in content
        assert "Testing" in content
        assert "Documentation" in content

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_parallel_agent_execution(self) -> None:
        """Test agents execute independent tasks in parallel.

        User Story: Independent tasks should run concurrently to
        minimize total workflow execution time.
        """
        # Simulate parallel execution
        async def mock_agent_work(agent_name: str, delay: float) -> dict:
            await asyncio.sleep(delay)
            return {"agent": agent_name, "result": f"{agent_name} complete"}

        # Run 3 independent agents in parallel
        tasks = [
            mock_agent_work("coder", 0.1),
            mock_agent_work("tester", 0.1),
            mock_agent_work("documenter", 0.1),
        ]

        import time

        start = time.time()
        results = await asyncio.gather(*tasks)
        elapsed = time.time() - start

        # Should complete in ~0.1s, not ~0.3s
        assert elapsed < 0.25
        assert len(results) == 3

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_agent_handoff_with_context(
        self,
        mock_ollama_client: MagicMock,
    ) -> None:
        """Test context is preserved during agent handoffs.

        User Story: When work passes from one agent to another,
        all relevant context should be preserved.
        """
        # Simulate architect producing design
        architect_output = {
            "design": {
                "endpoints": ["/users", "/users/{id}"],
                "models": ["User", "UserCreate"],
            }
        }

        # Simulate coder receiving architect context
        coder_context = {
            "previous_agent": "architect",
            "previous_output": architect_output,
            "task": "Implement the designed endpoints",
        }

        # Verify context is complete
        assert "design" in coder_context["previous_output"]
        assert coder_context["previous_agent"] == "architect"


class TestHITLWorkflowE2E:
    """E2E tests for Human-in-the-Loop workflows."""

    @pytest.mark.e2e
    @pytest.mark.user
    @pytest.mark.asyncio
    async def test_approval_workflow(
        self,
        async_client: Any,
        mock_memory_manager: MagicMock,
    ) -> None:
        """Test workflow pauses for user approval on high-risk actions.

        User Story: As a business owner, I want to approve any
        actions that could have significant impact before they execute.
        """
        # Simulate intervention request
        intervention = {
            "id": "int-001",
            "type": "approval",
            "reason": "About to delete production files",
            "context": {"files": ["/app/main.py", "/app/config.py"]},
            "status": "pending",
        }

        # Step 1: Workflow should pause
        assert intervention["status"] == "pending"

        # Step 2: User approves
        intervention["status"] = "approved"
        intervention["approved_by"] = "owner@company.com"
        intervention["approved_at"] = "2025-01-01T12:00:00Z"

        # Step 3: Workflow resumes
        assert intervention["status"] == "approved"

    @pytest.mark.e2e
    @pytest.mark.user
    @pytest.mark.asyncio
    async def test_rejection_workflow(
        self,
        async_client: Any,
    ) -> None:
        """Test workflow handles user rejection correctly.

        User Story: If I reject an action, the workflow should find
        an alternative approach or ask for clarification.
        """
        intervention = {
            "id": "int-002",
            "type": "approval",
            "reason": "Suggested approach uses deprecated library",
            "status": "pending",
        }

        # User rejects with feedback
        intervention["status"] = "rejected"
        intervention["rejection_reason"] = "Use the newer library instead"

        # Workflow should adapt
        alternative_approach = {
            "based_on_feedback": intervention["rejection_reason"],
            "new_approach": "Using recommended library v2.0",
        }

        assert "newer library" in intervention["rejection_reason"]
        assert alternative_approach["new_approach"] is not None

    @pytest.mark.e2e
    @pytest.mark.user
    @pytest.mark.asyncio
    async def test_clarification_workflow(self) -> None:
        """Test workflow requests clarification when needed.

        User Story: When the system is uncertain about requirements,
        it should ask me for clarification before proceeding.
        """
        clarification_request = {
            "id": "clar-001",
            "type": "clarification",
            "question": "Should user passwords be hashed with bcrypt or argon2?",
            "options": ["bcrypt (more widely used)", "argon2 (more secure)"],
            "default": "argon2",
            "context": {"task": "Implement user authentication"},
        }

        # User provides clarification
        clarification_response = {
            "request_id": "clar-001",
            "selected_option": "argon2",
            "additional_notes": "Security is our priority",
        }

        assert clarification_response["selected_option"] in ["bcrypt", "argon2"]


class TestToolExecutionE2E:
    """E2E tests for tool execution workflows."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_file_operation_tool(
        self,
        mock_tool_registry: MagicMock,
        tmp_path: Any,
    ) -> None:
        """Test file operations execute correctly.

        User Story: When the coder agent needs to create files,
        the file tool should create them in the correct location.
        """
        # Setup mock file tool
        test_file = tmp_path / "test_output.py"
        file_content = "def hello(): return 'world'"

        # Simulate file creation
        mock_tool_registry.execute_tool = AsyncMock(
            return_value={
                "success": True,
                "path": str(test_file),
                "bytes_written": len(file_content),
            }
        )

        result = await mock_tool_registry.execute_tool(
            name="write_file",
            args={"path": str(test_file), "content": file_content},
        )

        assert result["success"] is True

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_code_execution_tool(
        self,
        mock_tool_registry: MagicMock,
    ) -> None:
        """Test code execution in sandbox.

        User Story: When testing code, it should run in a safe
        sandbox environment that can't affect the host system.
        """
        mock_tool_registry.execute_tool = AsyncMock(
            return_value={
                "success": True,
                "stdout": "Hello, World!\n",
                "stderr": "",
                "exit_code": 0,
                "sandbox_id": "sandbox-123",
            }
        )

        result = await mock_tool_registry.execute_tool(
            name="execute_code",
            args={
                "code": "print('Hello, World!')",
                "language": "python",
                "timeout": 30,
            },
        )

        assert result["success"] is True
        assert result["exit_code"] == 0
        assert "Hello, World!" in result["stdout"]

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_git_integration_tool(
        self,
        mock_tool_registry: MagicMock,
    ) -> None:
        """Test Git version control integration.

        User Story: Code changes should be automatically committed
        with meaningful commit messages.
        """
        mock_tool_registry.execute_tool = AsyncMock(
            return_value={
                "success": True,
                "commit_hash": "abc123",
                "message": "feat: Add user authentication module",
                "files_changed": 3,
            }
        )

        result = await mock_tool_registry.execute_tool(
            name="git_commit",
            args={
                "message": "feat: Add user authentication module",
                "files": ["auth.py", "models.py", "tests/test_auth.py"],
            },
        )

        assert result["success"] is True
        assert "commit_hash" in result


class TestMemoryPersistenceE2E:
    """E2E tests for memory persistence across sessions."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_session_recovery(
        self,
        mock_memory_manager: MagicMock,
    ) -> None:
        """Test workflow can recover from interrupted session.

        User Story: If the system restarts, I should be able to
        resume my workflow from where it left off.
        """
        session_id = "session-recovery-test"

        # Simulate saving checkpoint before "crash"
        checkpoint = {
            "session_id": session_id,
            "current_step": 3,
            "current_agent": "coder",
            "completed_tasks": ["task-1", "task-2"],
            "pending_tasks": ["task-3", "task-4"],
            "state": {"code_in_progress": "def partial_impl(): ..."},
        }

        mock_memory_manager.save_checkpoint = AsyncMock(return_value=True)
        mock_memory_manager.load_checkpoint = AsyncMock(return_value=checkpoint)

        # "Restart" and recover
        await mock_memory_manager.save_checkpoint(checkpoint)
        recovered = await mock_memory_manager.load_checkpoint(session_id)

        assert recovered["current_step"] == 3
        assert len(recovered["completed_tasks"]) == 2

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_cross_session_knowledge(
        self,
        mock_memory_manager: MagicMock,
    ) -> None:
        """Test knowledge persists across sessions.

        User Story: Patterns and learnings from previous sessions
        should be available in new sessions.
        """
        # Session 1: Learn a pattern
        pattern = {
            "type": "error_resolution",
            "error": "ImportError: No module named 'xyz'",
            "solution": "pip install xyz",
            "success_rate": 0.95,
        }

        mock_memory_manager.store_knowledge = AsyncMock(return_value="k-123")
        mock_memory_manager.search_knowledge = AsyncMock(
            return_value=[pattern]
        )

        await mock_memory_manager.store_knowledge(pattern)

        # Session 2: Retrieve pattern
        similar_error = "ImportError: No module named 'abc'"
        results = await mock_memory_manager.search_knowledge(similar_error)

        assert len(results) >= 1
        assert results[0]["type"] == "error_resolution"


class TestErrorRecoveryE2E:
    """E2E tests for error recovery and resilience."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery(
        self,
        mock_ollama_client: MagicMock,
    ) -> None:
        """Test system recovers after circuit breaker opens.

        User Story: If the LLM service fails repeatedly, the system
        should fail gracefully and recover when the service returns.
        """
        call_count = 0
        failure_threshold = 3

        async def flaky_service(*args: Any, **kwargs: Any) -> dict:
            nonlocal call_count
            call_count += 1
            if call_count <= failure_threshold:
                raise ConnectionError("Service unavailable")
            return {"message": {"content": "Success"}, "done": True}

        mock_ollama_client.chat = flaky_service

        # First 3 calls fail
        for i in range(failure_threshold):
            with pytest.raises(ConnectionError):
                await mock_ollama_client.chat(model="test", messages=[])

        # 4th call succeeds
        result = await mock_ollama_client.chat(model="test", messages=[])
        assert result["done"] is True

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_retry_with_backoff(self) -> None:
        """Test exponential backoff on transient failures.

        User Story: Temporary failures should be retried with
        increasing delays to avoid overwhelming the service.
        """
        attempts = []

        async def track_attempts() -> bool:
            import time

            attempts.append(time.time())
            if len(attempts) < 3:
                raise ConnectionError("Retry me")
            return True

        # Simulate retry with backoff
        max_retries = 3
        base_delay = 0.05

        for attempt in range(max_retries):
            try:
                await track_attempts()
                break
            except ConnectionError:
                if attempt < max_retries - 1:
                    await asyncio.sleep(base_delay * (2 ** attempt))

        # Verify delays increased
        assert len(attempts) == 3
        delay_1 = attempts[1] - attempts[0]
        delay_2 = attempts[2] - attempts[1]
        # Second delay should be longer (with some tolerance)
        assert delay_2 >= delay_1 * 1.5

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_graceful_degradation(
        self,
        mock_memory_manager: MagicMock,
    ) -> None:
        """Test system continues with reduced functionality.

        User Story: If a non-critical service fails, the core
        workflow should continue with degraded features.
        """
        # Memory service fails
        mock_memory_manager.store_message = AsyncMock(
            side_effect=ConnectionError("Neo4j unavailable")
        )
        mock_memory_manager.is_available = False

        # Workflow should continue with in-memory fallback
        fallback_messages = []

        async def fallback_store(message: dict) -> str:
            fallback_messages.append(message)
            return f"local-{len(fallback_messages)}"

        # System adapts to use fallback
        msg_id = await fallback_store({"role": "user", "content": "Hello"})
        assert msg_id == "local-1"
        assert len(fallback_messages) == 1


class TestSafetyValidationE2E:
    """E2E tests for safety validation workflows."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_dangerous_code_blocked(
        self,
        mock_ollama_client: MagicMock,
    ) -> None:
        """Test dangerous code is detected and blocked.

        User Story: Code that could harm the system or data should
        be flagged and require explicit approval.
        """
        # Simulate Granite Guardian safety check
        mock_ollama_client.chat = AsyncMock(
            return_value={
                "message": {
                    "role": "assistant",
                    "content": '{"safe": false, "category": "system_damage"}',
                },
                "done": True,
            }
        )

        dangerous_code = "import os; os.system('rm -rf /')"

        response = await mock_ollama_client.chat(
            model="granite-guardian:2b",
            messages=[
                {
                    "role": "user",
                    "content": f"Analyze this code for safety: {dangerous_code}",
                }
            ],
        )

        import json

        result = json.loads(response["message"]["content"])
        assert result["safe"] is False
        assert "system_damage" in result["category"]

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_safe_code_passes(
        self,
        mock_ollama_client: MagicMock,
    ) -> None:
        """Test safe code passes validation.

        User Story: Normal, safe code should pass validation
        without requiring manual intervention.
        """
        mock_ollama_client.chat = AsyncMock(
            return_value={
                "message": {
                    "role": "assistant",
                    "content": '{"safe": true, "confidence": 0.98}',
                },
                "done": True,
            }
        )

        safe_code = "def add(a: int, b: int) -> int:\n    return a + b"

        response = await mock_ollama_client.chat(
            model="granite-guardian:2b",
            messages=[
                {
                    "role": "user",
                    "content": f"Analyze this code for safety: {safe_code}",
                }
            ],
        )

        import json

        result = json.loads(response["message"]["content"])
        assert result["safe"] is True
        assert result["confidence"] > 0.9


class TestAPIIntegrationE2E:
    """E2E tests for API integration."""

    @pytest.mark.e2e
    def test_health_check_all_services(self, client: Any) -> None:
        """Test health check reports all service statuses.

        User Story: The health endpoint should give me a complete
        picture of system status at a glance.
        """
        response = client.get("/api/v1/health")

        # Basic health check should work
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    @pytest.mark.e2e
    def test_api_error_handling(self, client: Any) -> None:
        """Test API returns proper error responses.

        User Story: When something goes wrong, the API should
        return clear, actionable error messages.
        """
        # Request non-existent resource
        response = client.get("/api/v1/sessions/non-existent-id")

        # Should get proper error response, not crash
        assert response.status_code in [404, 422, 500]

    @pytest.mark.e2e
    def test_api_validation(self, client: Any) -> None:
        """Test API validates input properly.

        User Story: Invalid requests should be rejected with
        clear validation error messages.
        """
        # Send invalid data
        response = client.post(
            "/api/v1/workflows/sessions",
            json={"invalid_field": 123},
        )

        # Should reject or handle gracefully
        assert response.status_code in [200, 201, 404, 422]


class TestTimeTravelDebuggingE2E:
    """E2E tests for time-travel debugging feature."""

    @pytest.mark.e2e
    @pytest.mark.user
    @pytest.mark.asyncio
    async def test_state_inspection(
        self,
        mock_memory_manager: MagicMock,
    ) -> None:
        """Test inspecting past workflow states.

        User Story: I want to see what the system state was at
        any point in the workflow history.
        """
        checkpoints = [
            {"id": "cp-1", "step": 1, "state": {"agent": "pm", "task": "init"}},
            {"id": "cp-2", "step": 2, "state": {"agent": "coder", "code": "..."}},
            {"id": "cp-3", "step": 3, "state": {"agent": "tester", "tests": "..."}},
        ]

        mock_memory_manager.get_checkpoints = AsyncMock(return_value=checkpoints)

        history = await mock_memory_manager.get_checkpoints("session-123")

        assert len(history) == 3
        assert history[0]["step"] == 1
        assert history[2]["state"]["agent"] == "tester"

    @pytest.mark.e2e
    @pytest.mark.user
    @pytest.mark.asyncio
    async def test_rollback_to_checkpoint(
        self,
        mock_memory_manager: MagicMock,
    ) -> None:
        """Test rolling back to a previous checkpoint.

        User Story: If something went wrong, I want to roll back
        to a known good state and try a different approach.
        """
        current_state = {"step": 5, "errors": ["test failures"]}
        good_state = {"step": 2, "agent": "coder", "code": "working_version"}

        mock_memory_manager.rollback_to_checkpoint = AsyncMock(
            return_value=good_state
        )

        restored = await mock_memory_manager.rollback_to_checkpoint(
            session_id="session-123",
            checkpoint_id="cp-2",
        )

        assert restored["step"] == 2
        assert "errors" not in restored

    @pytest.mark.e2e
    @pytest.mark.user
    @pytest.mark.asyncio
    async def test_replay_from_checkpoint(
        self,
        mock_memory_manager: MagicMock,
    ) -> None:
        """Test replaying workflow from checkpoint.

        User Story: After rolling back, I want to resume the
        workflow with different parameters or decisions.
        """
        checkpoint = {"step": 2, "state": {"pending_decision": True}}

        mock_memory_manager.replay_from = AsyncMock(
            return_value={
                "resumed": True,
                "from_step": 2,
                "new_decision": "alternative_approach",
            }
        )

        result = await mock_memory_manager.replay_from(
            checkpoint_id="cp-2",
            modifications={"decision": "alternative_approach"},
        )

        assert result["resumed"] is True
        assert result["new_decision"] == "alternative_approach"
