"""Time-travel debugging for workflow state inspection and rollback.

This module provides capabilities for inspecting historical workflow
states and rolling back to previous checkpoints when needed.
"""

import copy
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CheckpointType(str, Enum):
    """Types of checkpoints."""

    AUTO = "auto"
    MANUAL = "manual"
    INTERVENTION = "intervention"
    ERROR = "error"
    MILESTONE = "milestone"


class RollbackStatus(str, Enum):
    """Status of a rollback operation."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StateSnapshot(BaseModel):
    """A snapshot of workflow state at a point in time.

    Attributes:
        snapshot_id: Unique identifier for the snapshot.
        workflow_id: The workflow this snapshot belongs to.
        checkpoint_type: Type of checkpoint.
        state_data: The captured state data.
        metadata: Additional metadata about the snapshot.
        created_at: When the snapshot was created.
        agent_id: Agent active when snapshot was created.
        node_id: Graph node active when snapshot was created.
        iteration: Workflow iteration number.
        description: Human-readable description.
        tags: Tags for categorization.
    """

    snapshot_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str
    checkpoint_type: CheckpointType = CheckpointType.AUTO
    state_data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    agent_id: str | None = None
    node_id: str | None = None
    iteration: int = 0
    description: str = ""
    tags: list[str] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}


class StateDiff(BaseModel):
    """Difference between two state snapshots.

    Attributes:
        from_snapshot_id: Starting snapshot.
        to_snapshot_id: Ending snapshot.
        added_keys: Keys added in the new state.
        removed_keys: Keys removed from the new state.
        modified_keys: Keys with changed values.
        changes: Detailed change information.
    """

    from_snapshot_id: str
    to_snapshot_id: str
    added_keys: list[str] = Field(default_factory=list)
    removed_keys: list[str] = Field(default_factory=list)
    modified_keys: list[str] = Field(default_factory=list)
    changes: dict[str, dict[str, Any]] = Field(default_factory=dict)


class RollbackRequest(BaseModel):
    """A request to rollback to a previous state.

    Attributes:
        request_id: Unique identifier.
        workflow_id: The workflow to roll back.
        target_snapshot_id: Snapshot to roll back to.
        reason: Reason for the rollback.
        preserve_logs: Whether to preserve logs.
        status: Current status.
        created_at: When the request was created.
        completed_at: When the rollback completed.
        error_message: Error if rollback failed.
    """

    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str
    target_snapshot_id: str
    reason: str = ""
    preserve_logs: bool = True
    status: RollbackStatus = RollbackStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    error_message: str = ""


@dataclass
class TimeTravelConfig:
    """Configuration for time-travel debugging.

    Attributes:
        max_snapshots_per_workflow: Maximum snapshots to keep.
        auto_checkpoint_interval: Auto-checkpoint every N iterations.
        checkpoint_on_intervention: Auto-checkpoint on intervention.
        checkpoint_on_error: Auto-checkpoint on errors.
        deep_copy_state: Use deep copy for state capture.
        compress_snapshots: Compress snapshot data.
    """

    max_snapshots_per_workflow: int = 100
    auto_checkpoint_interval: int = 5
    checkpoint_on_intervention: bool = True
    checkpoint_on_error: bool = True
    deep_copy_state: bool = True
    compress_snapshots: bool = False


class TimeTravelDebugger:
    """Time-travel debugger for workflow state management.

    Provides capabilities for creating checkpoints, inspecting
    historical states, comparing states, and rolling back.
    """

    def __init__(self, config: TimeTravelConfig | None = None) -> None:
        """Initialize the time-travel debugger.

        Args:
            config: Configuration for the debugger.
        """
        self.config = config or TimeTravelConfig()
        self._snapshots: dict[str, list[StateSnapshot]] = {}
        self._rollback_requests: dict[str, RollbackRequest] = {}

    def create_checkpoint(
        self,
        workflow_id: str,
        state_data: dict[str, Any],
        checkpoint_type: CheckpointType = CheckpointType.AUTO,
        agent_id: str | None = None,
        node_id: str | None = None,
        iteration: int = 0,
        description: str = "",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StateSnapshot:
        """Create a checkpoint of the current state.

        Args:
            workflow_id: The workflow ID.
            state_data: The state data to capture.
            checkpoint_type: Type of checkpoint.
            agent_id: Active agent.
            node_id: Active graph node.
            iteration: Current iteration.
            description: Human description.
            tags: Tags for the checkpoint.
            metadata: Additional metadata.

        Returns:
            The created snapshot.
        """
        # Deep copy state if configured
        if self.config.deep_copy_state:
            captured_state = copy.deepcopy(state_data)
        else:
            captured_state = state_data.copy()

        snapshot = StateSnapshot(
            workflow_id=workflow_id,
            checkpoint_type=checkpoint_type,
            state_data=captured_state,
            agent_id=agent_id,
            node_id=node_id,
            iteration=iteration,
            description=description,
            tags=tags or [],
            metadata=metadata or {},
        )

        # Store snapshot
        if workflow_id not in self._snapshots:
            self._snapshots[workflow_id] = []

        self._snapshots[workflow_id].append(snapshot)

        # Enforce maximum snapshots
        self._enforce_snapshot_limit(workflow_id)

        logger.debug(
            f"Created checkpoint {snapshot.snapshot_id} "
            f"for workflow {workflow_id}"
        )

        return snapshot

    def _enforce_snapshot_limit(self, workflow_id: str) -> None:
        """Enforce the maximum snapshot limit.

        Args:
            workflow_id: The workflow ID.
        """
        snapshots = self._snapshots.get(workflow_id, [])
        max_count = self.config.max_snapshots_per_workflow

        if len(snapshots) > max_count:
            # Keep manual and milestone checkpoints longer
            protected_types = {CheckpointType.MANUAL, CheckpointType.MILESTONE}

            # Separate protected and unprotected
            protected = [s for s in snapshots if s.checkpoint_type in
                         protected_types]
            unprotected = [s for s in snapshots if s.checkpoint_type not in
                           protected_types]

            # Remove oldest unprotected first
            while len(protected) + len(unprotected) > max_count:
                if unprotected:
                    unprotected.pop(0)
                elif protected:
                    protected.pop(0)
                else:
                    break

            self._snapshots[workflow_id] = protected + unprotected

    def get_snapshot(self, snapshot_id: str) -> StateSnapshot | None:
        """Get a snapshot by ID.

        Args:
            snapshot_id: The snapshot ID.

        Returns:
            The snapshot or None.
        """
        for snapshots in self._snapshots.values():
            for snapshot in snapshots:
                if snapshot.snapshot_id == snapshot_id:
                    return snapshot
        return None

    def get_workflow_snapshots(
        self,
        workflow_id: str,
        checkpoint_type: CheckpointType | None = None,
        tags: list[str] | None = None,
        limit: int | None = None,
    ) -> list[StateSnapshot]:
        """Get snapshots for a workflow.

        Args:
            workflow_id: The workflow ID.
            checkpoint_type: Optional filter by type.
            tags: Optional filter by tags.
            limit: Maximum number to return.

        Returns:
            List of snapshots.
        """
        snapshots = self._snapshots.get(workflow_id, [])

        if checkpoint_type:
            snapshots = [
                s for s in snapshots
                if s.checkpoint_type == checkpoint_type
            ]

        if tags:
            snapshots = [
                s for s in snapshots
                if any(t in s.tags for t in tags)
            ]

        # Sort by creation time, newest first
        snapshots = sorted(
            snapshots,
            key=lambda s: s.created_at,
            reverse=True,
        )

        if limit:
            snapshots = snapshots[:limit]

        return snapshots

    def get_latest_snapshot(
        self,
        workflow_id: str,
    ) -> StateSnapshot | None:
        """Get the latest snapshot for a workflow.

        Args:
            workflow_id: The workflow ID.

        Returns:
            The latest snapshot or None.
        """
        snapshots = self.get_workflow_snapshots(workflow_id, limit=1)
        return snapshots[0] if snapshots else None

    def get_snapshot_at_iteration(
        self,
        workflow_id: str,
        iteration: int,
    ) -> StateSnapshot | None:
        """Get snapshot at or before a specific iteration.

        Args:
            workflow_id: The workflow ID.
            iteration: The iteration number.

        Returns:
            The closest snapshot at or before the iteration.
        """
        snapshots = self._snapshots.get(workflow_id, [])

        # Filter to snapshots at or before the iteration
        valid_snapshots = [
            s for s in snapshots
            if s.iteration <= iteration
        ]

        if not valid_snapshots:
            return None

        # Return the one closest to the requested iteration
        return max(valid_snapshots, key=lambda s: s.iteration)

    def compare_snapshots(
        self,
        from_snapshot_id: str,
        to_snapshot_id: str,
    ) -> StateDiff | None:
        """Compare two snapshots and return the differences.

        Args:
            from_snapshot_id: Starting snapshot ID.
            to_snapshot_id: Ending snapshot ID.

        Returns:
            The differences or None if snapshots not found.
        """
        from_snapshot = self.get_snapshot(from_snapshot_id)
        to_snapshot = self.get_snapshot(to_snapshot_id)

        if not from_snapshot or not to_snapshot:
            return None

        from_state = from_snapshot.state_data
        to_state = to_snapshot.state_data

        # Calculate differences
        from_keys = set(from_state.keys())
        to_keys = set(to_state.keys())

        added_keys = list(to_keys - from_keys)
        removed_keys = list(from_keys - to_keys)

        modified_keys = []
        changes: dict[str, dict[str, Any]] = {}

        for key in from_keys & to_keys:
            if from_state[key] != to_state[key]:
                modified_keys.append(key)
                changes[key] = {
                    "from": from_state[key],
                    "to": to_state[key],
                }

        # Add added keys to changes
        for key in added_keys:
            changes[key] = {
                "from": None,
                "to": to_state[key],
            }

        # Add removed keys to changes
        for key in removed_keys:
            changes[key] = {
                "from": from_state[key],
                "to": None,
            }

        return StateDiff(
            from_snapshot_id=from_snapshot_id,
            to_snapshot_id=to_snapshot_id,
            added_keys=added_keys,
            removed_keys=removed_keys,
            modified_keys=modified_keys,
            changes=changes,
        )

    def request_rollback(
        self,
        workflow_id: str,
        target_snapshot_id: str,
        reason: str = "",
        preserve_logs: bool = True,
    ) -> RollbackRequest:
        """Request a rollback to a previous state.

        Args:
            workflow_id: The workflow ID.
            target_snapshot_id: Snapshot to roll back to.
            reason: Reason for the rollback.
            preserve_logs: Whether to preserve logs.

        Returns:
            The rollback request.

        Raises:
            ValueError: If the snapshot is not found.
        """
        # Verify the snapshot exists
        snapshot = self.get_snapshot(target_snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot not found: {target_snapshot_id}")

        if snapshot.workflow_id != workflow_id:
            raise ValueError("Snapshot does not belong to this workflow")

        request = RollbackRequest(
            workflow_id=workflow_id,
            target_snapshot_id=target_snapshot_id,
            reason=reason,
            preserve_logs=preserve_logs,
        )

        self._rollback_requests[request.request_id] = request

        logger.info(
            f"Rollback requested for workflow {workflow_id} "
            f"to snapshot {target_snapshot_id}"
        )

        return request

    def execute_rollback(
        self,
        request_id: str,
    ) -> dict[str, Any]:
        """Execute a rollback request.

        Args:
            request_id: The rollback request ID.

        Returns:
            The restored state data.

        Raises:
            ValueError: If the request is not found or invalid.
        """
        request = self._rollback_requests.get(request_id)
        if not request:
            raise ValueError(f"Rollback request not found: {request_id}")

        if request.status not in [
            RollbackStatus.PENDING,
            RollbackStatus.FAILED,
        ]:
            raise ValueError(f"Cannot execute request in status: "
                             f"{request.status.value}")

        # Get the target snapshot
        snapshot = self.get_snapshot(request.target_snapshot_id)
        if not snapshot:
            request.status = RollbackStatus.FAILED
            request.error_message = "Target snapshot not found"
            raise ValueError("Target snapshot not found")

        try:
            request.status = RollbackStatus.IN_PROGRESS

            # Get the state to restore
            if self.config.deep_copy_state:
                restored_state = copy.deepcopy(snapshot.state_data)
            else:
                restored_state = snapshot.state_data.copy()

            # If preserving logs, we might want to keep certain keys
            # This is a placeholder for more sophisticated log handling

            # Mark completed
            request.status = RollbackStatus.COMPLETED
            request.completed_at = datetime.utcnow()

            # Create a new checkpoint marking the rollback
            self.create_checkpoint(
                workflow_id=request.workflow_id,
                state_data=restored_state,
                checkpoint_type=CheckpointType.MANUAL,
                description=f"Rollback to {request.target_snapshot_id}",
                tags=["rollback"],
                metadata={
                    "rollback_request_id": request_id,
                    "original_snapshot_id": request.target_snapshot_id,
                },
            )

            logger.info(
                f"Rollback {request_id} completed successfully"
            )

            return restored_state

        except Exception as e:
            request.status = RollbackStatus.FAILED
            request.error_message = str(e)
            logger.error(f"Rollback {request_id} failed: {e}")
            raise

    def get_rollback_request(
        self,
        request_id: str,
    ) -> RollbackRequest | None:
        """Get a rollback request by ID.

        Args:
            request_id: The request ID.

        Returns:
            The request or None.
        """
        return self._rollback_requests.get(request_id)

    def cancel_rollback(self, request_id: str) -> bool:
        """Cancel a pending rollback request.

        Args:
            request_id: The request ID.

        Returns:
            True if cancelled successfully.
        """
        request = self._rollback_requests.get(request_id)
        if not request:
            return False

        if request.status != RollbackStatus.PENDING:
            return False

        request.status = RollbackStatus.CANCELLED
        return True

    def get_state_timeline(
        self,
        workflow_id: str,
        key: str,
    ) -> list[dict[str, Any]]:
        """Get the timeline of values for a specific state key.

        Args:
            workflow_id: The workflow ID.
            key: The state key to track.

        Returns:
            List of value changes over time.
        """
        snapshots = self._snapshots.get(workflow_id, [])
        snapshots = sorted(snapshots, key=lambda s: s.created_at)

        timeline: list[dict[str, Any]] = []
        previous_value = None

        for snapshot in snapshots:
            current_value = snapshot.state_data.get(key)
            if current_value != previous_value:
                timeline.append({
                    "snapshot_id": snapshot.snapshot_id,
                    "timestamp": snapshot.created_at.isoformat(),
                    "iteration": snapshot.iteration,
                    "value": current_value,
                    "node_id": snapshot.node_id,
                    "agent_id": snapshot.agent_id,
                })
                previous_value = current_value

        return timeline

    def search_snapshots(
        self,
        workflow_id: str,
        query: dict[str, Any],
    ) -> list[StateSnapshot]:
        """Search snapshots for states matching a query.

        Args:
            workflow_id: The workflow ID.
            query: Dictionary of key-value pairs to match.

        Returns:
            List of matching snapshots.
        """
        snapshots = self._snapshots.get(workflow_id, [])
        matches: list[StateSnapshot] = []

        for snapshot in snapshots:
            state = snapshot.state_data
            if all(
                key in state and state[key] == value
                for key, value in query.items()
            ):
                matches.append(snapshot)

        return sorted(matches, key=lambda s: s.created_at, reverse=True)

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a snapshot.

        Args:
            snapshot_id: The snapshot ID.

        Returns:
            True if deleted successfully.
        """
        for workflow_id, snapshots in self._snapshots.items():
            for i, snapshot in enumerate(snapshots):
                if snapshot.snapshot_id == snapshot_id:
                    del self._snapshots[workflow_id][i]
                    logger.debug(f"Deleted snapshot {snapshot_id}")
                    return True
        return False

    def clear_workflow_snapshots(self, workflow_id: str) -> int:
        """Clear all snapshots for a workflow.

        Args:
            workflow_id: The workflow ID.

        Returns:
            Number of snapshots cleared.
        """
        if workflow_id not in self._snapshots:
            return 0

        count = len(self._snapshots[workflow_id])
        del self._snapshots[workflow_id]
        return count


# Helper functions


def create_error_checkpoint(
    debugger: TimeTravelDebugger,
    workflow_id: str,
    state_data: dict[str, Any],
    error: Exception,
    agent_id: str | None = None,
    node_id: str | None = None,
) -> StateSnapshot:
    """Create an error checkpoint for debugging.

    Args:
        debugger: The time-travel debugger.
        workflow_id: The workflow ID.
        state_data: Current state data.
        error: The error that occurred.
        agent_id: Active agent.
        node_id: Active node.

    Returns:
        The created snapshot.
    """
    return debugger.create_checkpoint(
        workflow_id=workflow_id,
        state_data=state_data,
        checkpoint_type=CheckpointType.ERROR,
        agent_id=agent_id,
        node_id=node_id,
        description=f"Error: {type(error).__name__}: {str(error)}",
        tags=["error", type(error).__name__],
        metadata={
            "error_type": type(error).__name__,
            "error_message": str(error),
        },
    )


def create_milestone_checkpoint(
    debugger: TimeTravelDebugger,
    workflow_id: str,
    state_data: dict[str, Any],
    milestone: str,
    agent_id: str | None = None,
) -> StateSnapshot:
    """Create a milestone checkpoint.

    Args:
        debugger: The time-travel debugger.
        workflow_id: The workflow ID.
        state_data: Current state data.
        milestone: Description of the milestone.
        agent_id: Active agent.

    Returns:
        The created snapshot.
    """
    return debugger.create_checkpoint(
        workflow_id=workflow_id,
        state_data=state_data,
        checkpoint_type=CheckpointType.MILESTONE,
        agent_id=agent_id,
        description=f"Milestone: {milestone}",
        tags=["milestone"],
    )


# Global instance


_time_travel_debugger: TimeTravelDebugger | None = None


def get_time_travel_debugger() -> TimeTravelDebugger:
    """Get the global time-travel debugger.

    Returns:
        The global TimeTravelDebugger instance.
    """
    global _time_travel_debugger
    if _time_travel_debugger is None:
        _time_travel_debugger = TimeTravelDebugger()
    return _time_travel_debugger
