"""Loop detection and timeout mechanisms for workflow execution.

This module provides mechanisms to detect infinite loops, stuck workflows,
and enforce timeouts to prevent runaway agent execution.
"""

import asyncio
import hashlib
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from app.core.exceptions import LoopDetectedError, WorkflowTimeoutError

logger = logging.getLogger(__name__)


class StuckCondition(str, Enum):
    """Types of stuck conditions that can be detected."""

    INFINITE_LOOP = "infinite_loop"
    STATE_REPETITION = "state_repetition"
    NO_PROGRESS = "no_progress"
    TIMEOUT = "timeout"
    FAILED_TOOL_CALLS = "failed_tool_calls"
    AGENT_WAITING = "agent_waiting"


class LoopType(str, Enum):
    """Legacy loop type classification."""

    INFINITE_LOOP = "infinite_loop"
    STATE_REPEAT = "state_repeat"
    TIMEOUT = "timeout"
    NO_PROGRESS = "no_progress"


class LoopSeverity(str, Enum):
    """Legacy loop severity classification."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class LoopEvent:
    """Legacy loop event model for compatibility."""

    workflow_id: str
    loop_type: LoopType
    severity: LoopSeverity
    description: str
    event_id: str = field(default_factory=lambda: str(datetime.utcnow().timestamp()))
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class LoopDetectionConfig:
    """Configuration for loop detection.

    Attributes:
        max_iterations: Maximum number of iterations before declaring a loop.
        max_state_repetitions: Max times the same state can repeat.
        state_history_size: Number of recent states to track.
        progress_check_interval: Seconds between progress checks.
        min_progress_threshold: Minimum progress required per interval.
        timeout_seconds: Maximum execution time in seconds.
        failed_tool_call_threshold: Max consecutive failed tool calls.
    """

    max_iterations: int = 100
    max_state_repetitions: int = 3
    state_history_size: int = 20
    progress_check_interval: float = 30.0
    min_progress_threshold: float = 0.01
    timeout_seconds: float = 600.0
    failed_tool_call_threshold: int = 5
    state_repeat_threshold: int = 3

    def __post_init__(self) -> None:
        if self.max_state_repetitions == 3 and self.state_repeat_threshold != 3:
            self.max_state_repetitions = self.state_repeat_threshold


@dataclass
class LoopDetectionMetrics:
    """Metrics for loop detection.

    Attributes:
        workflow_id: The workflow being monitored.
        iteration_count: Current iteration count.
        start_time: When monitoring started.
        last_progress_time: Last time progress was detected.
        state_repetition_counts: Counts of repeated states.
        consecutive_failed_tools: Count of consecutive tool failures.
        detected_conditions: List of detected stuck conditions.
    """

    workflow_id: str
    iteration_count: int = 0
    start_time: datetime = field(default_factory=datetime.utcnow)
    last_progress_time: datetime = field(default_factory=datetime.utcnow)
    state_repetition_counts: dict[str, int] = field(default_factory=dict)
    consecutive_failed_tools: int = 0
    detected_conditions: list[StuckCondition] = field(default_factory=list)


class StateHasher:
    """Utility for hashing workflow states for comparison."""

    @staticmethod
    def hash_state(state: dict[str, Any]) -> str:
        """Create a hash of a workflow state.

        Args:
            state: The state dictionary to hash.

        Returns:
            A hex string hash of the state.
        """
        # Extract key fields that indicate meaningful state change
        relevant_fields = [
            "current_agent",
            "pending_tasks",
            "completed_tasks",
            "agent_outputs",
        ]

        state_str = ""
        for field in relevant_fields:
            if field in state:
                value = state[field]
                if isinstance(value, (list, dict)):
                    state_str += f"{field}:{len(value)};"
                else:
                    state_str += f"{field}:{value};"

        return hashlib.md5(state_str.encode()).hexdigest()

    @staticmethod
    def states_equivalent(
        state1: dict[str, Any],
        state2: dict[str, Any],
    ) -> bool:
        """Check if two states are equivalent.

        Args:
            state1: First state to compare.
            state2: Second state to compare.

        Returns:
            True if states are equivalent.
        """
        hash1 = StateHasher.hash_state(state1)
        hash2 = StateHasher.hash_state(state2)
        return hash1 == hash2


class LoopDetector:
    """Detector for infinite loops and stuck conditions in workflows.

    Monitors workflow execution for various stuck conditions including
    infinite loops, state repetition, lack of progress, and timeouts.
    """

    def __init__(
        self,
        config: LoopDetectionConfig | None = None,
    ) -> None:
        """Initialize the loop detector.

        Args:
            config: Configuration for detection thresholds.
        """
        self.config = config or LoopDetectionConfig()
        self._workflows: dict[str, LoopDetectionMetrics] = {}
        self._state_history: dict[str, deque[str]] = {}
        self._progress_tracker: dict[str, float] = {}

    def start_monitoring(self, workflow_id: str) -> None:
        """Start monitoring a workflow.

        Args:
            workflow_id: The workflow ID to monitor.
        """
        now = datetime.utcnow()
        self._workflows[workflow_id] = LoopDetectionMetrics(
            workflow_id=workflow_id,
            start_time=now,
            last_progress_time=now,
        )
        self._state_history[workflow_id] = deque(
            maxlen=self.config.state_history_size
        )
        self._progress_tracker[workflow_id] = 0.0
        logger.debug(f"Started loop monitoring for workflow: {workflow_id}")

    def stop_monitoring(self, workflow_id: str) -> None:
        """Stop monitoring a workflow.

        Args:
            workflow_id: The workflow ID to stop monitoring.
        """
        self._workflows.pop(workflow_id, None)
        self._state_history.pop(workflow_id, None)
        self._progress_tracker.pop(workflow_id, None)
        logger.debug(f"Stopped loop monitoring for workflow: {workflow_id}")

    def record_iteration(
        self,
        workflow_id: str,
        state: dict[str, Any] | None = None,
        agent_id: str | None = None,
        state_hash: str | None = None,
    ) -> list[StuckCondition]:
        """Record a workflow iteration and check for stuck conditions.

        Args:
            workflow_id: The workflow ID.
            state: Current workflow state.

        Returns:
            List of detected stuck conditions.

        Raises:
            LoopDetectedError: If an unrecoverable loop is detected.
            WorkflowTimeoutError: If the workflow has timed out.
        """
        if workflow_id not in self._workflows:
            self.start_monitoring(workflow_id)

        metrics = self._workflows[workflow_id]
        metrics.iteration_count += 1

        detected: list[StuckCondition] = []

        # Check iteration limit
        if metrics.iteration_count >= self.config.max_iterations:
            detected.append(StuckCondition.INFINITE_LOOP)
            if state_hash is None:
                raise LoopDetectedError(
                    f"Maximum iterations ({self.config.max_iterations}) exceeded",
                    workflow_id=workflow_id,
                    iteration_count=metrics.iteration_count,
                )

        # Check timeout
        elapsed = (datetime.utcnow() - metrics.start_time).total_seconds()
        if elapsed >= self.config.timeout_seconds:
            detected.append(StuckCondition.TIMEOUT)
            if state_hash is None:
                raise WorkflowTimeoutError(
                    f"Workflow timed out after {elapsed:.1f}s",
                    workflow_id=workflow_id,
                    timeout_seconds=int(self.config.timeout_seconds),
                )

        # Check state repetition
        if state is None:
            state = {"current_agent": agent_id}
        state_hash = state_hash or StateHasher.hash_state(state)
        history = self._state_history[workflow_id]

        if state_hash in metrics.state_repetition_counts:
            metrics.state_repetition_counts[state_hash] += 1
            count = metrics.state_repetition_counts[state_hash]

            if count >= self.config.max_state_repetitions:
                detected.append(StuckCondition.STATE_REPETITION)
                logger.warning(
                    f"State repeated {count} times in workflow {workflow_id}"
                )
        else:
            metrics.state_repetition_counts[state_hash] = 1

        history.append(state_hash)

        # Check for progress
        if not self._check_progress(workflow_id, state):
            detected.append(StuckCondition.NO_PROGRESS)

        metrics.detected_conditions.extend(detected)
        return detected

    def check_for_loops(self, workflow_id: str) -> LoopEvent | None:
        """Return a LoopEvent if a loop condition is detected."""
        metrics = self._workflows.get(workflow_id)
        if metrics is None:
            return None

        if metrics.iteration_count > self.config.max_iterations:
            return LoopEvent(
                workflow_id=workflow_id,
                loop_type=LoopType.INFINITE_LOOP,
                severity=LoopSeverity.HIGH,
                description="Maximum iterations exceeded",
            )

        if metrics.state_repetition_counts:
            max_repeat = max(metrics.state_repetition_counts.values())
            if max_repeat >= self.config.max_state_repetitions:
                return LoopEvent(
                    workflow_id=workflow_id,
                    loop_type=LoopType.STATE_REPEAT,
                    severity=LoopSeverity.MEDIUM,
                    description="Repeated state detected",
                )

        elapsed = (datetime.utcnow() - metrics.start_time).total_seconds()
        if elapsed >= self.config.timeout_seconds:
            return LoopEvent(
                workflow_id=workflow_id,
                loop_type=LoopType.TIMEOUT,
                severity=LoopSeverity.HIGH,
                description="Workflow timed out",
            )

        return None

    def get_iteration_count(self, workflow_id: str) -> int:
        metrics = self._workflows.get(workflow_id)
        return metrics.iteration_count if metrics else 0

    def clear_workflow(self, workflow_id: str) -> None:
        """Clear tracking for a workflow (compat)."""
        self._workflows.pop(workflow_id, None)
        self._state_history.pop(workflow_id, None)
        self._progress_tracker.pop(workflow_id, None)

    def record_tool_call_result(
        self,
        workflow_id: str,
        success: bool,
    ) -> list[StuckCondition]:
        """Record a tool call result.

        Args:
            workflow_id: The workflow ID.
            success: Whether the tool call succeeded.

        Returns:
            List of detected stuck conditions.
        """
        if workflow_id not in self._workflows:
            return []

        metrics = self._workflows[workflow_id]
        detected: list[StuckCondition] = []

        if success:
            metrics.consecutive_failed_tools = 0
            metrics.last_progress_time = datetime.utcnow()
        else:
            metrics.consecutive_failed_tools += 1

            if (
                metrics.consecutive_failed_tools
                >= self.config.failed_tool_call_threshold
            ):
                detected.append(StuckCondition.FAILED_TOOL_CALLS)
                logger.warning(
                    f"Workflow {workflow_id} has "
                    f"{metrics.consecutive_failed_tools} consecutive "
                    "failed tool calls"
                )

        return detected

    def record_progress(
        self,
        workflow_id: str,
        progress: float,
    ) -> None:
        """Record progress made by a workflow.

        Args:
            workflow_id: The workflow ID.
            progress: Progress value (0.0 to 1.0).
        """
        if workflow_id not in self._workflows:
            return

        self._progress_tracker[workflow_id] = progress
        self._workflows[workflow_id].last_progress_time = datetime.utcnow()

    def get_metrics(self, workflow_id: str) -> LoopDetectionMetrics | None:
        """Get metrics for a workflow.

        Args:
            workflow_id: The workflow ID.

        Returns:
            Metrics or None if not monitored.
        """
        return self._workflows.get(workflow_id)

    def _check_progress(
        self,
        workflow_id: str,
        state: dict[str, Any],
    ) -> bool:
        """Check if the workflow is making progress.

        Args:
            workflow_id: The workflow ID.
            state: Current workflow state.

        Returns:
            True if progress is being made.
        """
        metrics = self._workflows[workflow_id]
        elapsed_since_progress = (
            datetime.utcnow() - metrics.last_progress_time
        ).total_seconds()

        if elapsed_since_progress > self.config.progress_check_interval:
            # Check if completed tasks have increased
            completed = state.get("completed_tasks", [])
            if isinstance(completed, list) and len(completed) > 0:
                metrics.last_progress_time = datetime.utcnow()
                return True

            # Check progress tracker
            current_progress = self._progress_tracker.get(workflow_id, 0.0)
            if current_progress >= self.config.min_progress_threshold:
                return True

            return False

        return True


class TimeoutManager:
    """Manager for workflow timeouts.

    Provides async timeout handling for workflow operations.
    """

    def __init__(
        self,
        default_timeout: float = 300.0,
    ) -> None:
        """Initialize the timeout manager.

        Args:
            default_timeout: Default timeout in seconds.
        """
        self.default_timeout = default_timeout
        self._timeouts: dict[str, float] = {}
        self._start_times: dict[str, float] = {}

    def set_timeout(
        self,
        workflow_id: str,
        timeout: float | None = None,
    ) -> None:
        """Set a timeout for a workflow.

        Args:
            workflow_id: The workflow ID.
            timeout: Timeout in seconds (uses default if None).
        """
        self._timeouts[workflow_id] = timeout or self.default_timeout
        self._start_times[workflow_id] = time.time()

    def check_timeout(self, workflow_id: str) -> bool:
        """Check if a workflow has timed out.

        Args:
            workflow_id: The workflow ID.

        Returns:
            True if timed out.
        """
        if workflow_id not in self._start_times:
            return False

        elapsed = time.time() - self._start_times[workflow_id]
        timeout = self._timeouts.get(workflow_id, self.default_timeout)
        return elapsed >= timeout

    def get_remaining(self, workflow_id: str) -> float:
        """Get remaining time before timeout.

        Args:
            workflow_id: The workflow ID.

        Returns:
            Remaining seconds (0 if timed out or not tracked).
        """
        if workflow_id not in self._start_times:
            return 0.0

        elapsed = time.time() - self._start_times[workflow_id]
        timeout = self._timeouts.get(workflow_id, self.default_timeout)
        return max(0.0, timeout - elapsed)

    def clear(self, workflow_id: str) -> None:
        """Clear timeout tracking for a workflow.

        Args:
            workflow_id: The workflow ID.
        """
        self._timeouts.pop(workflow_id, None)
        self._start_times.pop(workflow_id, None)

    async def with_timeout(
        self,
        workflow_id: str,
        coro: Any,
        timeout: float | None = None,
    ) -> Any:
        """Execute a coroutine with timeout.

        Args:
            workflow_id: The workflow ID for error reporting.
            coro: The coroutine to execute.
            timeout: Timeout in seconds (uses default if None).

        Returns:
            The coroutine result.

        Raises:
            WorkflowTimeoutError: If the operation times out.
        """
        timeout_seconds = timeout or self.default_timeout

        try:
            return await asyncio.wait_for(coro, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            raise WorkflowTimeoutError(
                f"Operation timed out after {timeout_seconds}s",
                workflow_id=workflow_id,
                timeout_seconds=int(timeout_seconds),
            ) from None


class RecoveryStrategy(str, Enum):
    """Strategies for recovering from stuck conditions."""

    RETRY = "retry"
    SKIP = "skip"
    ROLLBACK = "rollback"
    ESCALATE = "escalate"
    TERMINATE = "terminate"


@dataclass
class RecoveryAction:
    """Action to take for stuck condition recovery.

    Attributes:
        condition: The stuck condition to handle.
        strategy: The recovery strategy to use.
        max_retries: Maximum retry attempts.
        delay_seconds: Delay before retry.
        fallback_strategy: Strategy if primary fails.
    """

    condition: StuckCondition
    strategy: RecoveryStrategy
    max_retries: int = 3
    delay_seconds: float = 1.0
    fallback_strategy: RecoveryStrategy = RecoveryStrategy.ESCALATE


class StuckConditionHandler:
    """Handler for recovering from stuck conditions.

    Provides configurable recovery strategies for different
    types of stuck conditions.
    """

    def __init__(self) -> None:
        """Initialize the stuck condition handler."""
        self._actions: dict[StuckCondition, RecoveryAction] = {
            StuckCondition.INFINITE_LOOP: RecoveryAction(
                condition=StuckCondition.INFINITE_LOOP,
                strategy=RecoveryStrategy.TERMINATE,
            ),
            StuckCondition.STATE_REPETITION: RecoveryAction(
                condition=StuckCondition.STATE_REPETITION,
                strategy=RecoveryStrategy.SKIP,
                max_retries=2,
            ),
            StuckCondition.NO_PROGRESS: RecoveryAction(
                condition=StuckCondition.NO_PROGRESS,
                strategy=RecoveryStrategy.ESCALATE,
            ),
            StuckCondition.TIMEOUT: RecoveryAction(
                condition=StuckCondition.TIMEOUT,
                strategy=RecoveryStrategy.TERMINATE,
            ),
            StuckCondition.FAILED_TOOL_CALLS: RecoveryAction(
                condition=StuckCondition.FAILED_TOOL_CALLS,
                strategy=RecoveryStrategy.RETRY,
                max_retries=5,
                delay_seconds=2.0,
            ),
            StuckCondition.AGENT_WAITING: RecoveryAction(
                condition=StuckCondition.AGENT_WAITING,
                strategy=RecoveryStrategy.ESCALATE,
            ),
        }
        self._retry_counts: dict[str, dict[StuckCondition, int]] = {}

    def configure_action(
        self,
        condition: StuckCondition,
        action: RecoveryAction,
    ) -> None:
        """Configure recovery action for a condition.

        Args:
            condition: The condition to configure.
            action: The recovery action to use.
        """
        self._actions[condition] = action

    def get_recovery_strategy(
        self,
        workflow_id: str,
        condition: StuckCondition,
    ) -> RecoveryStrategy:
        """Get the recovery strategy for a condition.

        Args:
            workflow_id: The workflow ID.
            condition: The stuck condition.

        Returns:
            The recovery strategy to use.
        """
        action = self._actions.get(condition)
        if not action:
            return RecoveryStrategy.ESCALATE

        # Initialize retry tracking
        if workflow_id not in self._retry_counts:
            self._retry_counts[workflow_id] = {}

        if condition not in self._retry_counts[workflow_id]:
            self._retry_counts[workflow_id][condition] = 0

        # Check if retries exhausted
        if action.strategy == RecoveryStrategy.RETRY:
            count = self._retry_counts[workflow_id][condition]
            if count >= action.max_retries:
                logger.warning(
                    f"Retry limit reached for {condition} in {workflow_id}, "
                    f"falling back to {action.fallback_strategy}"
                )
                return action.fallback_strategy

            self._retry_counts[workflow_id][condition] = count + 1

        return action.strategy

    def reset_retries(
        self,
        workflow_id: str,
        condition: StuckCondition | None = None,
    ) -> None:
        """Reset retry counts for a workflow.

        Args:
            workflow_id: The workflow ID.
            condition: Specific condition to reset (all if None).
        """
        if workflow_id not in self._retry_counts:
            return

        if condition:
            self._retry_counts[workflow_id].pop(condition, None)
        else:
            self._retry_counts.pop(workflow_id, None)

    def clear_workflow(self, workflow_id: str) -> None:
        """Clear all tracking for a workflow.

        Args:
            workflow_id: The workflow ID.
        """
        self._retry_counts.pop(workflow_id, None)


# Global instances
_loop_detector: LoopDetector | None = None
_timeout_manager: TimeoutManager | None = None
_stuck_handler: StuckConditionHandler | None = None


def get_loop_detector() -> LoopDetector:
    """Get the global loop detector.

    Returns:
        The global LoopDetector instance.
    """
    global _loop_detector
    if _loop_detector is None:
        _loop_detector = LoopDetector()
    return _loop_detector


def get_timeout_manager() -> TimeoutManager:
    """Get the global timeout manager.

    Returns:
        The global TimeoutManager instance.
    """
    global _timeout_manager
    if _timeout_manager is None:
        _timeout_manager = TimeoutManager()
    return _timeout_manager


def get_stuck_condition_handler() -> StuckConditionHandler:
    """Get the global stuck condition handler.

    Returns:
        The global StuckConditionHandler instance.
    """
    global _stuck_handler
    if _stuck_handler is None:
        _stuck_handler = StuckConditionHandler()
    return _stuck_handler
