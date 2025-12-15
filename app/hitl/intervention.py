"""Human-in-the-loop intervention points for workflow control.

This module provides mechanisms for human users to intervene in
workflow execution at critical decision points.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Coroutine

from pydantic import BaseModel, Field

from app.core.exceptions import (
    HumanInterventionRequired,
    InterventionTimeoutError,
)

logger = logging.getLogger(__name__)


class InterventionType(str, Enum):
    """Types of human interventions."""

    APPROVAL = "approval"
    REVIEW = "review"
    CLARIFICATION = "clarification"
    OVERRIDE = "override"
    REDIRECT = "redirect"
    ABORT = "abort"


class InterventionPriority(str, Enum):
    """Priority levels for intervention requests."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class InterventionStatus(str, Enum):
    """Status of an intervention request."""

    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class InterventionRequest(BaseModel):
    """A request for human intervention.

    Attributes:
        request_id: Unique identifier for the request.
        intervention_type: Type of intervention needed.
        priority: Priority level.
        workflow_id: Associated workflow ID.
        agent_id: Agent requesting intervention.
        context: Context data for the decision.
        prompt: Human-readable prompt.
        options: Available options if applicable.
        default_option: Default option if timeout occurs.
        status: Current status of the request.
        created_at: When the request was created.
        timeout_at: When the request will timeout.
        response: Human response if provided.
        responded_by: Who responded to the request.
        responded_at: When the response was provided.
    """

    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    intervention_type: InterventionType
    priority: InterventionPriority = InterventionPriority.MEDIUM
    workflow_id: str
    agent_id: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    prompt: str
    options: list[str] = Field(default_factory=list)
    default_option: str | None = None
    status: InterventionStatus = InterventionStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    timeout_at: datetime | None = None
    response: str | None = None
    responded_by: str | None = None
    responded_at: datetime | None = None

    model_config = {"arbitrary_types_allowed": True}


class InterventionResponse(BaseModel):
    """Response to an intervention request.

    Attributes:
        request_id: ID of the request being responded to.
        approved: Whether the request was approved.
        response: The selected response or input.
        modifications: Any modifications to the original proposal.
        reason: Reason for the decision.
        responded_by: Who provided the response.
    """

    request_id: str
    approved: bool
    response: str | None = None
    modifications: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None
    responded_by: str | None = None


@dataclass
class InterventionConfig:
    """Configuration for intervention handling.

    Attributes:
        default_timeout: Default timeout in seconds.
        auto_approve_low_priority: Auto-approve low priority requests.
        max_pending_requests: Maximum pending requests per workflow.
        escalation_threshold: Time before escalating priority.
        notification_handlers: Handlers for notifications.
    """

    default_timeout: float = 300.0
    auto_approve_low_priority: bool = False
    max_pending_requests: int = 10
    escalation_threshold: float = 120.0
    notification_handlers: list[
        Callable[[InterventionRequest], Coroutine[Any, Any, None]]
    ] = field(default_factory=list)


class InterventionPoint:
    """A point in the workflow where intervention can occur.

    Intervention points are registered in workflows to allow
    human oversight and control at critical decision points.
    """

    def __init__(
        self,
        point_id: str,
        intervention_type: InterventionType,
        condition: Callable[[dict[str, Any]], bool] | None = None,
        required: bool = False,
        auto_timeout_action: str | None = None,
    ) -> None:
        """Initialize an intervention point.

        Args:
            point_id: Unique identifier for this point.
            intervention_type: Type of intervention at this point.
            condition: Optional condition for triggering intervention.
            required: Whether intervention is always required.
            auto_timeout_action: Action to take on timeout.
        """
        self.point_id = point_id
        self.intervention_type = intervention_type
        self.condition = condition
        self.required = required
        self.auto_timeout_action = auto_timeout_action

    def should_intervene(self, state: dict[str, Any]) -> bool:
        """Check if intervention should be triggered.

        Args:
            state: Current workflow state.

        Returns:
            True if intervention should occur.
        """
        if self.required:
            return True

        if self.condition:
            return self.condition(state)

        return False


class InterventionManager:
    """Manager for human intervention requests.

    Handles the lifecycle of intervention requests including
    creation, notification, response handling, and timeouts.
    """

    def __init__(self, config: InterventionConfig | None = None) -> None:
        """Initialize the intervention manager.

        Args:
            config: Configuration for intervention handling.
        """
        self.config = config or InterventionConfig()
        self._requests: dict[str, InterventionRequest] = {}
        self._points: dict[str, InterventionPoint] = {}
        self._response_events: dict[str, asyncio.Event] = {}
        self._subscribers: list[
            Callable[[InterventionRequest], Coroutine[Any, Any, None]]
        ] = []

    def register_point(self, point: InterventionPoint) -> None:
        """Register an intervention point.

        Args:
            point: The intervention point to register.
        """
        self._points[point.point_id] = point
        logger.debug(f"Registered intervention point: {point.point_id}")

    def unregister_point(self, point_id: str) -> None:
        """Unregister an intervention point.

        Args:
            point_id: ID of the point to unregister.
        """
        self._points.pop(point_id, None)
        logger.debug(f"Unregistered intervention point: {point_id}")

    def subscribe(
        self,
        handler: Callable[
            [InterventionRequest], Coroutine[Any, Any, None]
        ],
    ) -> None:
        """Subscribe to intervention request notifications.

        Args:
            handler: Async handler for intervention requests.
        """
        self._subscribers.append(handler)

    async def create_request(
        self,
        intervention_type: InterventionType,
        workflow_id: str,
        prompt: str,
        agent_id: str | None = None,
        context: dict[str, Any] | None = None,
        options: list[str] | None = None,
        default_option: str | None = None,
        priority: InterventionPriority = InterventionPriority.MEDIUM,
        timeout: float | None = None,
    ) -> InterventionRequest:
        """Create an intervention request.

        Args:
            intervention_type: Type of intervention.
            workflow_id: Associated workflow ID.
            prompt: Human-readable prompt.
            agent_id: Agent making the request.
            context: Additional context.
            options: Available options.
            default_option: Default option on timeout.
            priority: Request priority.
            timeout: Custom timeout in seconds.

        Returns:
            The created intervention request.
        """
        timeout_seconds = timeout or self.config.default_timeout
        timeout_at = datetime.utcnow() + timedelta(seconds=timeout_seconds)

        request = InterventionRequest(
            intervention_type=intervention_type,
            workflow_id=workflow_id,
            agent_id=agent_id,
            prompt=prompt,
            context=context or {},
            options=options or [],
            default_option=default_option,
            priority=priority,
            timeout_at=timeout_at,
        )

        self._requests[request.request_id] = request
        self._response_events[request.request_id] = asyncio.Event()

        # Notify subscribers
        await self._notify_subscribers(request)

        logger.info(
            f"Created intervention request {request.request_id} "
            f"for workflow {workflow_id}"
        )

        return request

    async def _notify_subscribers(self, request: InterventionRequest) -> None:
        """Notify all subscribers of a new request.

        Args:
            request: The intervention request.
        """
        for handler in self._subscribers:
            try:
                await handler(request)
            except Exception as e:
                logger.error(f"Error in intervention handler: {e}")

        for handler in self.config.notification_handlers:
            try:
                await handler(request)
            except Exception as e:
                logger.error(f"Error in notification handler: {e}")

    async def wait_for_response(
        self,
        request_id: str,
        timeout: float | None = None,
    ) -> InterventionResponse:
        """Wait for a response to an intervention request.

        Args:
            request_id: The request ID to wait for.
            timeout: Override timeout in seconds.

        Returns:
            The intervention response.

        Raises:
            InterventionTimeoutError: If the request times out.
            ValueError: If the request is not found.
        """
        request = self._requests.get(request_id)
        if not request:
            raise ValueError(f"Request not found: {request_id}")

        event = self._response_events.get(request_id)
        if not event:
            raise ValueError(f"No event for request: {request_id}")

        # Calculate timeout
        if timeout:
            wait_timeout = timeout
        elif request.timeout_at:
            remaining = (request.timeout_at - datetime.utcnow()).total_seconds()
            wait_timeout = max(0, remaining)
        else:
            wait_timeout = self.config.default_timeout

        try:
            await asyncio.wait_for(event.wait(), timeout=wait_timeout)
        except asyncio.TimeoutError:
            # Handle timeout
            request.status = InterventionStatus.TIMEOUT

            if request.default_option:
                # Use default option
                return InterventionResponse(
                    request_id=request_id,
                    approved=True,
                    response=request.default_option,
                    reason="Timeout - using default option",
                )

            raise InterventionTimeoutError(
                f"Intervention request timed out after {wait_timeout}s",
                request_id=request_id,
                timeout_seconds=int(wait_timeout),
            ) from None

        # Get the response
        request = self._requests[request_id]
        return InterventionResponse(
            request_id=request_id,
            approved=request.status == InterventionStatus.APPROVED,
            response=request.response,
            responded_by=request.responded_by,
        )

    async def respond(
        self,
        request_id: str,
        response: str | None = None,
        approved: bool = True,
        modifications: dict[str, Any] | None = None,
        reason: str | None = None,
        responded_by: str | None = None,
    ) -> InterventionRequest:
        """Respond to an intervention request.

        Args:
            request_id: The request ID.
            response: The selected response.
            approved: Whether the request is approved.
            modifications: Any modifications.
            reason: Reason for the decision.
            responded_by: Who is responding.

        Returns:
            The updated request.

        Raises:
            ValueError: If the request is not found.
        """
        request = self._requests.get(request_id)
        if not request:
            raise ValueError(f"Request not found: {request_id}")

        if request.status not in [
            InterventionStatus.PENDING,
            InterventionStatus.IN_REVIEW,
        ]:
            raise ValueError(
                f"Cannot respond to request in status: {request.status}"
            )

        # Update request
        request.response = response
        request.responded_by = responded_by
        request.responded_at = datetime.utcnow()

        if approved:
            if modifications:
                request.status = InterventionStatus.MODIFIED
            else:
                request.status = InterventionStatus.APPROVED
        else:
            request.status = InterventionStatus.REJECTED

        # Signal the waiting coroutine
        event = self._response_events.get(request_id)
        if event:
            event.set()

        logger.info(
            f"Intervention {request_id} responded: {request.status.value}"
        )

        return request

    def get_request(self, request_id: str) -> InterventionRequest | None:
        """Get an intervention request by ID.

        Args:
            request_id: The request ID.

        Returns:
            The request or None.
        """
        return self._requests.get(request_id)

    def get_pending_requests(
        self,
        workflow_id: str | None = None,
    ) -> list[InterventionRequest]:
        """Get all pending intervention requests.

        Args:
            workflow_id: Optional filter by workflow.

        Returns:
            List of pending requests.
        """
        pending = [
            r for r in self._requests.values()
            if r.status == InterventionStatus.PENDING
        ]

        if workflow_id:
            pending = [r for r in pending if r.workflow_id == workflow_id]

        return sorted(pending, key=lambda r: r.created_at)

    def cancel_request(self, request_id: str) -> bool:
        """Cancel an intervention request.

        Args:
            request_id: The request ID.

        Returns:
            True if cancelled successfully.
        """
        request = self._requests.get(request_id)
        if not request:
            return False

        if request.status != InterventionStatus.PENDING:
            return False

        request.status = InterventionStatus.CANCELLED

        event = self._response_events.get(request_id)
        if event:
            event.set()

        return True

    def clear_workflow_requests(self, workflow_id: str) -> int:
        """Clear all requests for a workflow.

        Args:
            workflow_id: The workflow ID.

        Returns:
            Number of requests cleared.
        """
        to_remove = [
            r.request_id for r in self._requests.values()
            if r.workflow_id == workflow_id
        ]

        for request_id in to_remove:
            self.cancel_request(request_id)
            self._requests.pop(request_id, None)
            self._response_events.pop(request_id, None)

        return len(to_remove)


# Intervention helper functions


async def require_approval(
    manager: InterventionManager,
    workflow_id: str,
    prompt: str,
    agent_id: str | None = None,
    context: dict[str, Any] | None = None,
    options: list[str] | None = None,
    priority: InterventionPriority = InterventionPriority.MEDIUM,
    timeout: float | None = None,
) -> InterventionResponse:
    """Require human approval before proceeding.

    Args:
        manager: The intervention manager.
        workflow_id: The workflow ID.
        prompt: Prompt for the human.
        agent_id: The requesting agent.
        context: Additional context.
        options: Available options.
        priority: Request priority.
        timeout: Custom timeout.

    Returns:
        The intervention response.

    Raises:
        HumanInterventionRequired: If intervention is needed.
    """
    request = await manager.create_request(
        intervention_type=InterventionType.APPROVAL,
        workflow_id=workflow_id,
        prompt=prompt,
        agent_id=agent_id,
        context=context,
        options=options or ["Approve", "Reject"],
        default_option=None,
        priority=priority,
        timeout=timeout,
    )

    return await manager.wait_for_response(request.request_id)


async def request_clarification(
    manager: InterventionManager,
    workflow_id: str,
    prompt: str,
    agent_id: str | None = None,
    context: dict[str, Any] | None = None,
    timeout: float | None = None,
) -> str:
    """Request clarification from human.

    Args:
        manager: The intervention manager.
        workflow_id: The workflow ID.
        prompt: Question for the human.
        agent_id: The requesting agent.
        context: Additional context.
        timeout: Custom timeout.

    Returns:
        The human's clarification response.
    """
    request = await manager.create_request(
        intervention_type=InterventionType.CLARIFICATION,
        workflow_id=workflow_id,
        prompt=prompt,
        agent_id=agent_id,
        context=context,
        priority=InterventionPriority.MEDIUM,
        timeout=timeout,
    )

    response = await manager.wait_for_response(request.request_id)
    return response.response or ""


# Global instance


_intervention_manager: InterventionManager | None = None


def get_intervention_manager() -> InterventionManager:
    """Get the global intervention manager.

    Returns:
        The global InterventionManager instance.
    """
    global _intervention_manager
    if _intervention_manager is None:
        _intervention_manager = InterventionManager()
    return _intervention_manager
