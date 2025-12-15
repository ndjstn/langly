"""Unit tests for Human-in-the-Loop components.

Tests for intervention, approval, and time-travel debugging systems.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.hitl.intervention import (
    InterventionType,
    InterventionPriority,
    InterventionStatus,
    InterventionRequest,
    InterventionResponse,
    InterventionConfig,
    InterventionPoint,
    InterventionManager,
)
from app.hitl.approval import (
    ApprovalCategory,
    ApprovalDecision,
    RiskLevel,
    ApprovalRequest,
    ApprovalVote,
    ApprovalPolicy,
    ApprovalManager,
)
from app.hitl.time_travel import (
    CheckpointType,
    RollbackStatus,
    StateSnapshot,
    StateDiff,
    RollbackRequest,
    TimeTravelConfig,
    TimeTravelDebugger,
)


# =============================================================================
# Intervention Tests
# =============================================================================


class TestInterventionRequest:
    """Tests for InterventionRequest model."""

    def test_create_request_with_defaults(self) -> None:
        """Test creating a request with default values."""
        request = InterventionRequest(
            intervention_type=InterventionType.APPROVAL,
            workflow_id="test-workflow-123",
            prompt="Please approve this action",
        )

        assert request.request_id is not None
        assert request.intervention_type == InterventionType.APPROVAL
        assert request.workflow_id == "test-workflow-123"
        assert request.prompt == "Please approve this action"
        assert request.status == InterventionStatus.PENDING
        assert request.priority == InterventionPriority.MEDIUM

    def test_create_request_with_options(self) -> None:
        """Test creating a request with options."""
        request = InterventionRequest(
            intervention_type=InterventionType.REVIEW,
            workflow_id="test-workflow-123",
            prompt="Review this code",
            options=["Approve", "Request Changes", "Reject"],
            priority=InterventionPriority.HIGH,
        )

        assert request.options == ["Approve", "Request Changes", "Reject"]
        assert request.priority == InterventionPriority.HIGH


class TestInterventionPoint:
    """Tests for InterventionPoint class."""

    def test_required_intervention(self) -> None:
        """Test required intervention always triggers."""
        point = InterventionPoint(
            point_id="test-point",
            intervention_type=InterventionType.APPROVAL,
            required=True,
        )

        assert point.should_intervene({}) is True
        assert point.should_intervene({"any": "state"}) is True

    def test_conditional_intervention(self) -> None:
        """Test conditional intervention based on state."""
        condition = lambda state: state.get("needs_review", False)
        point = InterventionPoint(
            point_id="test-point",
            intervention_type=InterventionType.REVIEW,
            condition=condition,
            required=False,
        )

        assert point.should_intervene({}) is False
        assert point.should_intervene({"needs_review": False}) is False
        assert point.should_intervene({"needs_review": True}) is True


class TestInterventionManager:
    """Tests for InterventionManager class."""

    @pytest.fixture
    def manager(self) -> InterventionManager:
        """Create a test manager."""
        return InterventionManager()

    @pytest.mark.asyncio
    async def test_create_request(self, manager: InterventionManager) -> None:
        """Test creating an intervention request."""
        request = await manager.create_request(
            intervention_type=InterventionType.APPROVAL,
            workflow_id="test-workflow",
            prompt="Test prompt",
        )

        assert request.request_id is not None
        assert request.status == InterventionStatus.PENDING

        # Should be stored
        stored = manager.get_request(request.request_id)
        assert stored is not None
        assert stored.request_id == request.request_id

    @pytest.mark.asyncio
    async def test_respond_to_request(
        self, manager: InterventionManager
    ) -> None:
        """Test responding to an intervention request."""
        request = await manager.create_request(
            intervention_type=InterventionType.APPROVAL,
            workflow_id="test-workflow",
            prompt="Test prompt",
        )

        # Respond to request
        updated = await manager.respond(
            request_id=request.request_id,
            response="Approved",
            approved=True,
            responded_by="test-user",
        )

        assert updated.status == InterventionStatus.APPROVED
        assert updated.response == "Approved"
        assert updated.responded_by == "test-user"

    @pytest.mark.asyncio
    async def test_reject_request(self, manager: InterventionManager) -> None:
        """Test rejecting an intervention request."""
        request = await manager.create_request(
            intervention_type=InterventionType.APPROVAL,
            workflow_id="test-workflow",
            prompt="Test prompt",
        )

        updated = await manager.respond(
            request_id=request.request_id,
            response="Rejected",
            approved=False,
        )

        assert updated.status == InterventionStatus.REJECTED

    @pytest.mark.asyncio
    async def test_get_pending_requests(
        self, manager: InterventionManager
    ) -> None:
        """Test getting pending requests."""
        # Create multiple requests
        await manager.create_request(
            intervention_type=InterventionType.APPROVAL,
            workflow_id="workflow-1",
            prompt="Prompt 1",
        )
        await manager.create_request(
            intervention_type=InterventionType.REVIEW,
            workflow_id="workflow-2",
            prompt="Prompt 2",
        )

        pending = manager.get_pending_requests()
        assert len(pending) == 2

        # Filter by workflow
        pending_workflow1 = manager.get_pending_requests(
            workflow_id="workflow-1"
        )
        assert len(pending_workflow1) == 1

    def test_cancel_request(self, manager: InterventionManager) -> None:
        """Test cancelling a request."""
        # Create request synchronously using asyncio.run
        async def create() -> InterventionRequest:
            return await manager.create_request(
                intervention_type=InterventionType.APPROVAL,
                workflow_id="test-workflow",
                prompt="Test prompt",
            )

        request = asyncio.get_event_loop().run_until_complete(create())

        result = manager.cancel_request(request.request_id)
        assert result is True

        stored = manager.get_request(request.request_id)
        assert stored is not None
        assert stored.status == InterventionStatus.CANCELLED


# =============================================================================
# Approval Tests
# =============================================================================


class TestApprovalRequest:
    """Tests for ApprovalRequest model."""

    def test_create_approval_request(self) -> None:
        """Test creating an approval request."""
        request = ApprovalRequest(
            category=ApprovalCategory.CODE_EXECUTION,
            title="Execute Code",
            description="Execute generated Python code",
            workflow_id="test-workflow-123",
        )

        assert request.request_id is not None
        assert request.category == ApprovalCategory.CODE_EXECUTION
        assert request.decision == ApprovalDecision.PENDING
        assert request.risk_level == RiskLevel.MEDIUM

    def test_approval_with_risk_level(self) -> None:
        """Test approval request with specific risk level."""
        request = ApprovalRequest(
            category=ApprovalCategory.DEPLOYMENT,
            title="Deploy to Production",
            description="Deploy application to production",
            workflow_id="test-workflow-123",
            risk_level=RiskLevel.CRITICAL,
        )

        assert request.risk_level == RiskLevel.CRITICAL


class TestApprovalPolicy:
    """Tests for ApprovalPolicy dataclass."""

    def test_default_policy(self) -> None:
        """Test default policy values."""
        policy = ApprovalPolicy(category=ApprovalCategory.CODE_EXECUTION)

        assert policy.min_risk_for_approval == RiskLevel.MEDIUM
        assert policy.default_timeout == 600.0
        assert policy.required_approvers == 1

    def test_custom_policy(self) -> None:
        """Test custom policy values."""
        policy = ApprovalPolicy(
            category=ApprovalCategory.DEPLOYMENT,
            min_risk_for_approval=RiskLevel.LOW,
            default_timeout=900.0,
            required_approvers=2,
        )

        assert policy.min_risk_for_approval == RiskLevel.LOW
        assert policy.default_timeout == 900.0
        assert policy.required_approvers == 2


class TestApprovalManager:
    """Tests for ApprovalManager class."""

    @pytest.fixture
    def manager(self) -> ApprovalManager:
        """Create a test manager."""
        return ApprovalManager()

    @pytest.mark.asyncio
    async def test_create_approval_request(
        self, manager: ApprovalManager
    ) -> None:
        """Test creating an approval request."""
        request = await manager.create_request(
            category=ApprovalCategory.CODE_EXECUTION,
            title="Test Approval",
            description="Test description",
            workflow_id="test-workflow",
        )

        assert request.request_id is not None
        assert request.category == ApprovalCategory.CODE_EXECUTION
        assert request.decision == ApprovalDecision.PENDING

    @pytest.mark.asyncio
    async def test_vote_approval(self, manager: ApprovalManager) -> None:
        """Test voting on an approval request."""
        request = await manager.create_request(
            category=ApprovalCategory.FILE_MODIFICATION,
            title="Modify File",
            description="Modify configuration file",
            workflow_id="test-workflow",
        )

        vote = await manager.vote(
            request_id=request.request_id,
            approver_id="user-1",
            decision=ApprovalDecision.APPROVED,
            reason="Looks good",
        )

        assert vote.decision == ApprovalDecision.APPROVED

        # Check request is approved
        updated = manager.get_request(request.request_id)
        assert updated is not None
        assert updated.decision == ApprovalDecision.APPROVED

    @pytest.mark.asyncio
    async def test_vote_rejection(self, manager: ApprovalManager) -> None:
        """Test rejecting an approval request."""
        request = await manager.create_request(
            category=ApprovalCategory.SECURITY,
            title="Security Change",
            description="Change security settings",
            workflow_id="test-workflow",
        )

        await manager.vote(
            request_id=request.request_id,
            approver_id="user-1",
            decision=ApprovalDecision.REJECTED,
            reason="Security concern",
        )

        updated = manager.get_request(request.request_id)
        assert updated is not None
        assert updated.decision == ApprovalDecision.REJECTED

    def test_get_policy(self, manager: ApprovalManager) -> None:
        """Test getting approval policies."""
        policy = manager.get_policy(ApprovalCategory.CODE_EXECUTION)
        assert policy is not None
        assert policy.category == ApprovalCategory.CODE_EXECUTION

    def test_set_custom_policy(self, manager: ApprovalManager) -> None:
        """Test setting a custom policy."""
        custom_policy = ApprovalPolicy(
            category=ApprovalCategory.CODE_EXECUTION,
            min_risk_for_approval=RiskLevel.HIGH,
            required_approvers=3,
        )

        manager.set_policy(custom_policy)

        retrieved = manager.get_policy(ApprovalCategory.CODE_EXECUTION)
        assert retrieved is not None
        assert retrieved.required_approvers == 3


# =============================================================================
# Time-Travel Debugging Tests
# =============================================================================


class TestStateSnapshot:
    """Tests for StateSnapshot model."""

    def test_create_snapshot(self) -> None:
        """Test creating a state snapshot."""
        snapshot = StateSnapshot(
            workflow_id="test-workflow-123",
            state_data={"messages": [], "iteration": 5},
        )

        assert snapshot.snapshot_id is not None
        assert snapshot.workflow_id == "test-workflow-123"
        assert snapshot.state_data == {"messages": [], "iteration": 5}
        assert snapshot.checkpoint_type == CheckpointType.AUTO

    def test_snapshot_with_tags(self) -> None:
        """Test snapshot with tags."""
        snapshot = StateSnapshot(
            workflow_id="test-workflow-123",
            state_data={},
            checkpoint_type=CheckpointType.MILESTONE,
            tags=["important", "v1.0"],
        )

        assert snapshot.checkpoint_type == CheckpointType.MILESTONE
        assert "important" in snapshot.tags


class TestTimeTravelDebugger:
    """Tests for TimeTravelDebugger class."""

    @pytest.fixture
    def debugger(self) -> TimeTravelDebugger:
        """Create a test debugger."""
        return TimeTravelDebugger()

    def test_create_checkpoint(self, debugger: TimeTravelDebugger) -> None:
        """Test creating a checkpoint."""
        snapshot = debugger.create_checkpoint(
            workflow_id="test-workflow",
            state_data={"messages": [], "iteration": 1},
        )

        assert snapshot.snapshot_id is not None
        assert snapshot.workflow_id == "test-workflow"

    def test_get_snapshot(self, debugger: TimeTravelDebugger) -> None:
        """Test getting a snapshot by ID."""
        created = debugger.create_checkpoint(
            workflow_id="test-workflow",
            state_data={"test": "data"},
        )

        retrieved = debugger.get_snapshot(created.snapshot_id)
        assert retrieved is not None
        assert retrieved.snapshot_id == created.snapshot_id

    def test_get_workflow_snapshots(
        self, debugger: TimeTravelDebugger
    ) -> None:
        """Test getting snapshots for a workflow."""
        # Create multiple snapshots
        debugger.create_checkpoint(
            workflow_id="workflow-1",
            state_data={"iteration": 1},
        )
        debugger.create_checkpoint(
            workflow_id="workflow-1",
            state_data={"iteration": 2},
        )
        debugger.create_checkpoint(
            workflow_id="workflow-2",
            state_data={"iteration": 1},
        )

        snapshots = debugger.get_workflow_snapshots("workflow-1")
        assert len(snapshots) == 2

    def test_get_latest_snapshot(self, debugger: TimeTravelDebugger) -> None:
        """Test getting the latest snapshot."""
        debugger.create_checkpoint(
            workflow_id="test-workflow",
            state_data={"iteration": 1},
        )
        debugger.create_checkpoint(
            workflow_id="test-workflow",
            state_data={"iteration": 2},
        )

        latest = debugger.get_latest_snapshot("test-workflow")
        assert latest is not None
        assert latest.state_data["iteration"] == 2

    def test_compare_snapshots(self, debugger: TimeTravelDebugger) -> None:
        """Test comparing two snapshots."""
        snap1 = debugger.create_checkpoint(
            workflow_id="test-workflow",
            state_data={"value": 1, "name": "test"},
        )
        snap2 = debugger.create_checkpoint(
            workflow_id="test-workflow",
            state_data={"value": 2, "name": "test", "new_key": "added"},
        )

        diff = debugger.compare_snapshots(
            snap1.snapshot_id, snap2.snapshot_id
        )

        assert diff is not None
        assert "new_key" in diff.added_keys
        assert "value" in diff.modified_keys
        assert "name" not in diff.modified_keys

    def test_request_rollback(self, debugger: TimeTravelDebugger) -> None:
        """Test requesting a rollback."""
        snapshot = debugger.create_checkpoint(
            workflow_id="test-workflow",
            state_data={"iteration": 1},
        )

        request = debugger.request_rollback(
            workflow_id="test-workflow",
            target_snapshot_id=snapshot.snapshot_id,
            reason="Testing rollback",
        )

        assert request.request_id is not None
        assert request.status == RollbackStatus.PENDING
        assert request.target_snapshot_id == snapshot.snapshot_id

    def test_execute_rollback(self, debugger: TimeTravelDebugger) -> None:
        """Test executing a rollback."""
        snapshot = debugger.create_checkpoint(
            workflow_id="test-workflow",
            state_data={"iteration": 1, "data": "original"},
        )

        # Create more checkpoints to advance state
        debugger.create_checkpoint(
            workflow_id="test-workflow",
            state_data={"iteration": 5, "data": "modified"},
        )

        request = debugger.request_rollback(
            workflow_id="test-workflow",
            target_snapshot_id=snapshot.snapshot_id,
        )

        restored_state = debugger.execute_rollback(request.request_id)

        assert restored_state["iteration"] == 1
        assert restored_state["data"] == "original"

        # Check request status
        updated_request = debugger.get_rollback_request(request.request_id)
        assert updated_request is not None
        assert updated_request.status == RollbackStatus.COMPLETED

    def test_get_state_timeline(self, debugger: TimeTravelDebugger) -> None:
        """Test getting the timeline for a state key."""
        debugger.create_checkpoint(
            workflow_id="test-workflow",
            state_data={"counter": 0},
            iteration=0,
        )
        debugger.create_checkpoint(
            workflow_id="test-workflow",
            state_data={"counter": 5},
            iteration=5,
        )
        debugger.create_checkpoint(
            workflow_id="test-workflow",
            state_data={"counter": 10},
            iteration=10,
        )

        timeline = debugger.get_state_timeline("test-workflow", "counter")

        assert len(timeline) == 3
        assert timeline[0]["value"] == 0
        assert timeline[2]["value"] == 10

    def test_search_snapshots(self, debugger: TimeTravelDebugger) -> None:
        """Test searching snapshots by state query."""
        debugger.create_checkpoint(
            workflow_id="test-workflow",
            state_data={"status": "pending", "error": False},
        )
        debugger.create_checkpoint(
            workflow_id="test-workflow",
            state_data={"status": "error", "error": True},
        )
        debugger.create_checkpoint(
            workflow_id="test-workflow",
            state_data={"status": "complete", "error": False},
        )

        matches = debugger.search_snapshots(
            "test-workflow", {"error": True}
        )

        assert len(matches) == 1
        assert matches[0].state_data["status"] == "error"

    def test_delete_snapshot(self, debugger: TimeTravelDebugger) -> None:
        """Test deleting a snapshot."""
        snapshot = debugger.create_checkpoint(
            workflow_id="test-workflow",
            state_data={"test": "data"},
        )

        result = debugger.delete_snapshot(snapshot.snapshot_id)
        assert result is True

        # Should not be retrievable
        retrieved = debugger.get_snapshot(snapshot.snapshot_id)
        assert retrieved is None

    def test_clear_workflow_snapshots(
        self, debugger: TimeTravelDebugger
    ) -> None:
        """Test clearing all snapshots for a workflow."""
        debugger.create_checkpoint(
            workflow_id="test-workflow",
            state_data={"iteration": 1},
        )
        debugger.create_checkpoint(
            workflow_id="test-workflow",
            state_data={"iteration": 2},
        )

        count = debugger.clear_workflow_snapshots("test-workflow")

        assert count == 2
        assert len(debugger.get_workflow_snapshots("test-workflow")) == 0


# =============================================================================
# Integration Tests
# =============================================================================


class TestHITLIntegration:
    """Integration tests for HITL components."""

    @pytest.mark.asyncio
    async def test_intervention_to_approval_flow(self) -> None:
        """Test flow from intervention to approval."""
        intervention_manager = InterventionManager()
        approval_manager = ApprovalManager()

        # Create intervention request
        intervention = await intervention_manager.create_request(
            intervention_type=InterventionType.APPROVAL,
            workflow_id="test-workflow",
            prompt="Code execution requires approval",
            context={"code": "print('hello')"},
        )

        # If intervention requires approval, create approval request
        approval = await approval_manager.create_request(
            category=ApprovalCategory.CODE_EXECUTION,
            title=intervention.prompt,
            description="Approve code execution",
            workflow_id=intervention.workflow_id,
            action_data=intervention.context,
        )

        # Approve the request
        await approval_manager.vote(
            request_id=approval.request_id,
            approver_id="admin",
            decision=ApprovalDecision.APPROVED,
        )

        # Mark intervention as complete
        await intervention_manager.respond(
            request_id=intervention.request_id,
            approved=True,
            response="Approved via approval workflow",
        )

        # Verify states
        final_intervention = intervention_manager.get_request(
            intervention.request_id
        )
        final_approval = approval_manager.get_request(approval.request_id)

        assert final_intervention is not None
        assert final_intervention.status == InterventionStatus.APPROVED
        assert final_approval is not None
        assert final_approval.decision == ApprovalDecision.APPROVED

    def test_checkpoint_during_intervention(self) -> None:
        """Test creating checkpoints during interventions."""
        debugger = TimeTravelDebugger()

        # Simulate workflow state before intervention
        pre_intervention = debugger.create_checkpoint(
            workflow_id="test-workflow",
            state_data={"phase": "processing", "iteration": 5},
            checkpoint_type=CheckpointType.INTERVENTION,
            description="Before human review",
        )

        # After intervention is resolved
        post_intervention = debugger.create_checkpoint(
            workflow_id="test-workflow",
            state_data={"phase": "continuing", "iteration": 5},
            checkpoint_type=CheckpointType.INTERVENTION,
            description="After human review - approved",
        )

        # Both should be retrievable
        snapshots = debugger.get_workflow_snapshots(
            "test-workflow",
            checkpoint_type=CheckpointType.INTERVENTION,
        )

        assert len(snapshots) == 2
        assert any(s.description == "Before human review" for s in snapshots)
