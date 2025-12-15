"""Approval system for critical agent actions.

This module provides a comprehensive approval workflow for actions
that require human authorization before execution.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Coroutine

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ApprovalCategory(str, Enum):
    """Categories of actions requiring approval."""

    CODE_EXECUTION = "code_execution"
    FILE_MODIFICATION = "file_modification"
    DATABASE_CHANGE = "database_change"
    EXTERNAL_API = "external_api"
    DEPLOYMENT = "deployment"
    SECURITY = "security"
    COST_IMPACT = "cost_impact"
    DATA_DELETE = "data_delete"
    CONFIGURATION = "configuration"
    AGENT_SPAWN = "agent_spawn"


class ApprovalLevel(str, Enum):
    """Levels of approval required."""

    NONE = "none"
    INFORMATIONAL = "informational"
    SINGLE_APPROVAL = "single_approval"
    MULTI_APPROVAL = "multi_approval"
    ESCALATED = "escalated"


class ApprovalDecision(str, Enum):
    """Possible approval decisions."""

    PENDING = "pending"
    APPROVED = "approved"
    APPROVED_WITH_CHANGES = "approved_with_changes"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    EXPIRED = "expired"


class RiskLevel(str, Enum):
    """Risk levels for actions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ApprovalRequest(BaseModel):
    """A request for approval of an action.

    Attributes:
        request_id: Unique identifier for the request.
        category: Category of action.
        title: Short title for the approval.
        description: Detailed description of the action.
        risk_level: Assessed risk level.
        approval_level: Level of approval required.
        workflow_id: Associated workflow ID.
        agent_id: Agent requesting approval.
        action_data: Data about the proposed action.
        impact_summary: Summary of potential impacts.
        rollback_plan: Plan for rollback if needed.
        required_approvers: Number of approvers needed.
        current_approvers: List of current approvers.
        decision: Current decision status.
        created_at: When the request was created.
        expires_at: When the request expires.
        decided_at: When a decision was made.
        decision_reason: Reason for the decision.
        modifications: Any approved modifications.
    """

    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    category: ApprovalCategory
    title: str
    description: str
    risk_level: RiskLevel = RiskLevel.MEDIUM
    approval_level: ApprovalLevel = ApprovalLevel.SINGLE_APPROVAL
    workflow_id: str
    agent_id: str | None = None
    action_data: dict[str, Any] = Field(default_factory=dict)
    impact_summary: str = ""
    rollback_plan: str = ""
    required_approvers: int = 1
    current_approvers: list[str] = Field(default_factory=list)
    decision: ApprovalDecision = ApprovalDecision.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None
    decided_at: datetime | None = None
    decision_reason: str = ""
    modifications: dict[str, Any] = Field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}


class ApprovalVote(BaseModel):
    """A vote on an approval request.

    Attributes:
        vote_id: Unique identifier for the vote.
        request_id: The request being voted on.
        approver_id: Who is voting.
        decision: The vote decision.
        reason: Reason for the vote.
        modifications: Suggested modifications.
        voted_at: When the vote was cast.
    """

    vote_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    request_id: str
    approver_id: str
    decision: ApprovalDecision
    reason: str = ""
    modifications: dict[str, Any] = Field(default_factory=dict)
    voted_at: datetime = Field(default_factory=datetime.utcnow)


@dataclass
class ApprovalPolicy:
    """Policy configuration for approval workflows.

    Attributes:
        category: The action category this policy applies to.
        min_risk_for_approval: Minimum risk level requiring approval.
        default_timeout: Default timeout in seconds.
        required_approvers: Default number of approvers.
        auto_approve_conditions: Conditions for auto-approval.
        escalation_timeout: Time before escalation.
        escalation_level: Level to escalate to.
    """

    category: ApprovalCategory
    min_risk_for_approval: RiskLevel = RiskLevel.MEDIUM
    default_timeout: float = 600.0
    required_approvers: int = 1
    auto_approve_conditions: dict[str, Any] = field(default_factory=dict)
    escalation_timeout: float = 300.0
    escalation_level: ApprovalLevel = ApprovalLevel.ESCALATED


class ApprovalManager:
    """Manager for the approval workflow system.

    Handles creation, tracking, voting, and resolution of
    approval requests for critical actions.
    """

    def __init__(self) -> None:
        """Initialize the approval manager."""
        self._requests: dict[str, ApprovalRequest] = {}
        self._votes: dict[str, list[ApprovalVote]] = {}
        self._policies: dict[ApprovalCategory, ApprovalPolicy] = {}
        self._decision_events: dict[str, asyncio.Event] = {}
        self._subscribers: list[
            Callable[[ApprovalRequest], Coroutine[Any, Any, None]]
        ] = []

        # Initialize default policies
        self._init_default_policies()

    def _init_default_policies(self) -> None:
        """Initialize default approval policies."""
        # Code execution - high risk
        self._policies[ApprovalCategory.CODE_EXECUTION] = ApprovalPolicy(
            category=ApprovalCategory.CODE_EXECUTION,
            min_risk_for_approval=RiskLevel.MEDIUM,
            default_timeout=300.0,
            required_approvers=1,
        )

        # File modification - medium risk
        self._policies[ApprovalCategory.FILE_MODIFICATION] = ApprovalPolicy(
            category=ApprovalCategory.FILE_MODIFICATION,
            min_risk_for_approval=RiskLevel.HIGH,
            default_timeout=600.0,
            required_approvers=1,
        )

        # Database changes - high risk
        self._policies[ApprovalCategory.DATABASE_CHANGE] = ApprovalPolicy(
            category=ApprovalCategory.DATABASE_CHANGE,
            min_risk_for_approval=RiskLevel.MEDIUM,
            default_timeout=300.0,
            required_approvers=1,
        )

        # Deployment - critical
        self._policies[ApprovalCategory.DEPLOYMENT] = ApprovalPolicy(
            category=ApprovalCategory.DEPLOYMENT,
            min_risk_for_approval=RiskLevel.LOW,
            default_timeout=900.0,
            required_approvers=2,
        )

        # Security - always require approval
        self._policies[ApprovalCategory.SECURITY] = ApprovalPolicy(
            category=ApprovalCategory.SECURITY,
            min_risk_for_approval=RiskLevel.LOW,
            default_timeout=600.0,
            required_approvers=1,
        )

        # Data deletion - critical
        self._policies[ApprovalCategory.DATA_DELETE] = ApprovalPolicy(
            category=ApprovalCategory.DATA_DELETE,
            min_risk_for_approval=RiskLevel.LOW,
            default_timeout=600.0,
            required_approvers=1,
        )

    def set_policy(self, policy: ApprovalPolicy) -> None:
        """Set or update an approval policy.

        Args:
            policy: The approval policy to set.
        """
        self._policies[policy.category] = policy
        logger.debug(f"Set approval policy for {policy.category.value}")

    def get_policy(
        self,
        category: ApprovalCategory,
    ) -> ApprovalPolicy | None:
        """Get the policy for a category.

        Args:
            category: The action category.

        Returns:
            The policy or None.
        """
        return self._policies.get(category)

    def subscribe(
        self,
        handler: Callable[
            [ApprovalRequest], Coroutine[Any, Any, None]
        ],
    ) -> None:
        """Subscribe to approval request notifications.

        Args:
            handler: Async handler for approval requests.
        """
        self._subscribers.append(handler)

    async def create_request(
        self,
        category: ApprovalCategory,
        title: str,
        description: str,
        workflow_id: str,
        action_data: dict[str, Any] | None = None,
        agent_id: str | None = None,
        risk_level: RiskLevel | None = None,
        impact_summary: str = "",
        rollback_plan: str = "",
        timeout: float | None = None,
    ) -> ApprovalRequest:
        """Create an approval request.

        Args:
            category: Category of action.
            title: Short title.
            description: Detailed description.
            workflow_id: Associated workflow.
            action_data: Data about the action.
            agent_id: Requesting agent.
            risk_level: Override risk level.
            impact_summary: Summary of impacts.
            rollback_plan: Rollback strategy.
            timeout: Custom timeout in seconds.

        Returns:
            The created approval request.
        """
        policy = self._policies.get(category)

        # Determine approval level based on risk
        actual_risk = risk_level or self._assess_risk(category, action_data)
        approval_level = self._determine_approval_level(
            category, actual_risk, policy
        )

        # Calculate timeout
        timeout_seconds = timeout
        if timeout_seconds is None:
            timeout_seconds = policy.default_timeout if policy else 600.0
        expires_at = datetime.utcnow() + timedelta(seconds=timeout_seconds)

        # Determine required approvers
        required_approvers = 1
        if policy:
            required_approvers = policy.required_approvers

        request = ApprovalRequest(
            category=category,
            title=title,
            description=description,
            risk_level=actual_risk,
            approval_level=approval_level,
            workflow_id=workflow_id,
            agent_id=agent_id,
            action_data=action_data or {},
            impact_summary=impact_summary,
            rollback_plan=rollback_plan,
            required_approvers=required_approvers,
            expires_at=expires_at,
        )

        self._requests[request.request_id] = request
        self._votes[request.request_id] = []
        self._decision_events[request.request_id] = asyncio.Event()

        # Notify subscribers
        await self._notify_subscribers(request)

        logger.info(
            f"Created approval request {request.request_id} "
            f"for {category.value}"
        )

        return request

    def _assess_risk(
        self,
        category: ApprovalCategory,
        action_data: dict[str, Any] | None,
    ) -> RiskLevel:
        """Assess risk level for an action.

        Args:
            category: The action category.
            action_data: Data about the action.

        Returns:
            The assessed risk level.
        """
        # Default risk levels by category
        default_risks = {
            ApprovalCategory.CODE_EXECUTION: RiskLevel.HIGH,
            ApprovalCategory.FILE_MODIFICATION: RiskLevel.MEDIUM,
            ApprovalCategory.DATABASE_CHANGE: RiskLevel.HIGH,
            ApprovalCategory.EXTERNAL_API: RiskLevel.MEDIUM,
            ApprovalCategory.DEPLOYMENT: RiskLevel.CRITICAL,
            ApprovalCategory.SECURITY: RiskLevel.CRITICAL,
            ApprovalCategory.COST_IMPACT: RiskLevel.HIGH,
            ApprovalCategory.DATA_DELETE: RiskLevel.CRITICAL,
            ApprovalCategory.CONFIGURATION: RiskLevel.MEDIUM,
            ApprovalCategory.AGENT_SPAWN: RiskLevel.LOW,
        }

        base_risk = default_risks.get(category, RiskLevel.MEDIUM)

        # Adjust based on action data if provided
        if action_data:
            # Check for specific risk indicators
            if action_data.get("affects_production", False):
                if base_risk != RiskLevel.CRITICAL:
                    base_risk = RiskLevel.HIGH
            if action_data.get("irreversible", False):
                base_risk = RiskLevel.CRITICAL

        return base_risk

    def _determine_approval_level(
        self,
        category: ApprovalCategory,
        risk_level: RiskLevel,
        policy: ApprovalPolicy | None,
    ) -> ApprovalLevel:
        """Determine the required approval level.

        Args:
            category: The action category.
            risk_level: The assessed risk.
            policy: The applicable policy.

        Returns:
            The required approval level.
        """
        if policy:
            min_risk = policy.min_risk_for_approval
            risk_order = [
                RiskLevel.LOW, RiskLevel.MEDIUM,
                RiskLevel.HIGH, RiskLevel.CRITICAL,
            ]
            if risk_order.index(risk_level) < risk_order.index(min_risk):
                return ApprovalLevel.INFORMATIONAL

        if risk_level == RiskLevel.CRITICAL:
            return ApprovalLevel.MULTI_APPROVAL
        if risk_level == RiskLevel.HIGH:
            return ApprovalLevel.SINGLE_APPROVAL
        if risk_level == RiskLevel.MEDIUM:
            return ApprovalLevel.SINGLE_APPROVAL

        return ApprovalLevel.NONE

    async def _notify_subscribers(self, request: ApprovalRequest) -> None:
        """Notify subscribers of a new request.

        Args:
            request: The approval request.
        """
        for handler in self._subscribers:
            try:
                await handler(request)
            except Exception as e:
                logger.error(f"Error in approval handler: {e}")

    async def vote(
        self,
        request_id: str,
        approver_id: str,
        decision: ApprovalDecision,
        reason: str = "",
        modifications: dict[str, Any] | None = None,
    ) -> ApprovalVote:
        """Cast a vote on an approval request.

        Args:
            request_id: The request ID.
            approver_id: Who is voting.
            decision: The vote decision.
            reason: Reason for the vote.
            modifications: Suggested modifications.

        Returns:
            The created vote.

        Raises:
            ValueError: If the request is not found or already decided.
        """
        request = self._requests.get(request_id)
        if not request:
            raise ValueError(f"Request not found: {request_id}")

        if request.decision != ApprovalDecision.PENDING:
            raise ValueError(
                f"Request already decided: {request.decision.value}"
            )

        # Check for expiration
        if request.expires_at and datetime.utcnow() > request.expires_at:
            request.decision = ApprovalDecision.EXPIRED
            self._signal_decision(request_id)
            raise ValueError("Request has expired")

        # Check if approver already voted
        existing_votes = self._votes.get(request_id, [])
        for vote in existing_votes:
            if vote.approver_id == approver_id:
                raise ValueError("Approver has already voted")

        vote = ApprovalVote(
            request_id=request_id,
            approver_id=approver_id,
            decision=decision,
            reason=reason,
            modifications=modifications or {},
        )

        self._votes[request_id].append(vote)

        # Check if we have enough votes
        await self._evaluate_votes(request)

        logger.info(
            f"Vote cast on {request_id} by {approver_id}: {decision.value}"
        )

        return vote

    async def _evaluate_votes(self, request: ApprovalRequest) -> None:
        """Evaluate votes and make final decision.

        Args:
            request: The approval request.
        """
        votes = self._votes.get(request.request_id, [])

        # Count approvals and rejections
        approvals = [
            v for v in votes
            if v.decision in [
                ApprovalDecision.APPROVED,
                ApprovalDecision.APPROVED_WITH_CHANGES,
            ]
        ]
        rejections = [
            v for v in votes
            if v.decision == ApprovalDecision.REJECTED
        ]

        # Any rejection means rejected
        if rejections:
            request.decision = ApprovalDecision.REJECTED
            request.decided_at = datetime.utcnow()
            request.decision_reason = rejections[0].reason
            self._signal_decision(request.request_id)
            return

        # Check if we have enough approvals
        if len(approvals) >= request.required_approvers:
            # Collect all modifications
            all_modifications: dict[str, Any] = {}
            for vote in approvals:
                all_modifications.update(vote.modifications)

            if all_modifications:
                request.decision = ApprovalDecision.APPROVED_WITH_CHANGES
                request.modifications = all_modifications
            else:
                request.decision = ApprovalDecision.APPROVED

            request.decided_at = datetime.utcnow()
            request.current_approvers = [v.approver_id for v in approvals]
            self._signal_decision(request.request_id)

    def _signal_decision(self, request_id: str) -> None:
        """Signal that a decision has been made.

        Args:
            request_id: The request ID.
        """
        event = self._decision_events.get(request_id)
        if event:
            event.set()

    async def wait_for_decision(
        self,
        request_id: str,
        timeout: float | None = None,
    ) -> ApprovalRequest:
        """Wait for a decision on an approval request.

        Args:
            request_id: The request ID.
            timeout: Override timeout in seconds.

        Returns:
            The request with the decision.

        Raises:
            ValueError: If the request is not found.
            TimeoutError: If waiting times out.
        """
        request = self._requests.get(request_id)
        if not request:
            raise ValueError(f"Request not found: {request_id}")

        event = self._decision_events.get(request_id)
        if not event:
            raise ValueError(f"No event for request: {request_id}")

        # Calculate timeout
        if timeout:
            wait_timeout = timeout
        elif request.expires_at:
            remaining = (request.expires_at - datetime.utcnow()).total_seconds()
            wait_timeout = max(0, remaining)
        else:
            wait_timeout = 600.0

        try:
            await asyncio.wait_for(event.wait(), timeout=wait_timeout)
        except asyncio.TimeoutError:
            request.decision = ApprovalDecision.EXPIRED
            request.decided_at = datetime.utcnow()
            raise TimeoutError(
                f"Approval request timed out after {wait_timeout}s"
            ) from None

        return self._requests[request_id]

    def get_request(self, request_id: str) -> ApprovalRequest | None:
        """Get an approval request by ID.

        Args:
            request_id: The request ID.

        Returns:
            The request or None.
        """
        return self._requests.get(request_id)

    def get_votes(self, request_id: str) -> list[ApprovalVote]:
        """Get all votes for a request.

        Args:
            request_id: The request ID.

        Returns:
            List of votes.
        """
        return self._votes.get(request_id, [])

    def get_pending_requests(
        self,
        workflow_id: str | None = None,
        category: ApprovalCategory | None = None,
    ) -> list[ApprovalRequest]:
        """Get all pending approval requests.

        Args:
            workflow_id: Optional filter by workflow.
            category: Optional filter by category.

        Returns:
            List of pending requests.
        """
        pending = [
            r for r in self._requests.values()
            if r.decision == ApprovalDecision.PENDING
        ]

        if workflow_id:
            pending = [r for r in pending if r.workflow_id == workflow_id]

        if category:
            pending = [r for r in pending if r.category == category]

        return sorted(pending, key=lambda r: r.created_at)

    def cancel_request(self, request_id: str) -> bool:
        """Cancel an approval request.

        Args:
            request_id: The request ID.

        Returns:
            True if cancelled successfully.
        """
        request = self._requests.get(request_id)
        if not request:
            return False

        if request.decision != ApprovalDecision.PENDING:
            return False

        request.decision = ApprovalDecision.EXPIRED
        request.decided_at = datetime.utcnow()
        request.decision_reason = "Cancelled"
        self._signal_decision(request_id)

        return True


# Approval helper functions


async def require_approval(
    manager: ApprovalManager,
    category: ApprovalCategory,
    title: str,
    description: str,
    workflow_id: str,
    action_data: dict[str, Any] | None = None,
    agent_id: str | None = None,
    timeout: float | None = None,
) -> ApprovalRequest:
    """Require approval for an action.

    Args:
        manager: The approval manager.
        category: Category of action.
        title: Short title.
        description: Detailed description.
        workflow_id: Associated workflow.
        action_data: Data about the action.
        agent_id: Requesting agent.
        timeout: Custom timeout.

    Returns:
        The approved request.

    Raises:
        ValueError: If the request is rejected.
        TimeoutError: If the request times out.
    """
    request = await manager.create_request(
        category=category,
        title=title,
        description=description,
        workflow_id=workflow_id,
        action_data=action_data,
        agent_id=agent_id,
        timeout=timeout,
    )

    # Wait for decision
    result = await manager.wait_for_decision(request.request_id)

    if result.decision == ApprovalDecision.REJECTED:
        raise ValueError(f"Approval rejected: {result.decision_reason}")

    return result


def check_requires_approval(
    manager: ApprovalManager,
    category: ApprovalCategory,
    risk_level: RiskLevel | None = None,
) -> bool:
    """Check if an action requires approval.

    Args:
        manager: The approval manager.
        category: The action category.
        risk_level: Override risk level.

    Returns:
        True if approval is required.
    """
    policy = manager.get_policy(category)
    if not policy:
        return True  # Default to requiring approval

    actual_risk = risk_level or RiskLevel.MEDIUM
    min_risk = policy.min_risk_for_approval

    risk_order = [
        RiskLevel.LOW, RiskLevel.MEDIUM,
        RiskLevel.HIGH, RiskLevel.CRITICAL,
    ]

    return risk_order.index(actual_risk) >= risk_order.index(min_risk)


# Global instance


_approval_manager: ApprovalManager | None = None


def get_approval_manager() -> ApprovalManager:
    """Get the global approval manager.

    Returns:
        The global ApprovalManager instance.
    """
    global _approval_manager
    if _approval_manager is None:
        _approval_manager = ApprovalManager()
    return _approval_manager
