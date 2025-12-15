"""Human-in-the-Loop (HITL) integration module.

This module provides comprehensive human oversight and control
capabilities for the multi-agent workflow system.
"""

from app.hitl.intervention import (
    InterventionType,
    InterventionPriority,
    InterventionStatus,
    InterventionRequest,
    InterventionResponse,
    InterventionConfig,
    InterventionPoint,
    InterventionManager,
    require_approval,
    request_clarification,
    get_intervention_manager,
)

from app.hitl.approval import (
    ApprovalCategory,
    ApprovalLevel,
    ApprovalDecision,
    RiskLevel,
    ApprovalRequest,
    ApprovalVote,
    ApprovalPolicy,
    ApprovalManager,
    require_approval as require_approval_action,
    check_requires_approval,
    get_approval_manager,
)

from app.hitl.time_travel import (
    CheckpointType,
    RollbackStatus,
    StateSnapshot,
    StateDiff,
    RollbackRequest,
    TimeTravelConfig,
    TimeTravelDebugger,
    create_error_checkpoint,
    create_milestone_checkpoint,
    get_time_travel_debugger,
)


__all__ = [
    # Intervention types
    "InterventionType",
    "InterventionPriority",
    "InterventionStatus",
    "InterventionRequest",
    "InterventionResponse",
    "InterventionConfig",
    "InterventionPoint",
    "InterventionManager",
    "require_approval",
    "request_clarification",
    "get_intervention_manager",
    # Approval types
    "ApprovalCategory",
    "ApprovalLevel",
    "ApprovalDecision",
    "RiskLevel",
    "ApprovalRequest",
    "ApprovalVote",
    "ApprovalPolicy",
    "ApprovalManager",
    "require_approval_action",
    "check_requires_approval",
    "get_approval_manager",
    # Time-travel types
    "CheckpointType",
    "RollbackStatus",
    "StateSnapshot",
    "StateDiff",
    "RollbackRequest",
    "TimeTravelConfig",
    "TimeTravelDebugger",
    "create_error_checkpoint",
    "create_milestone_checkpoint",
    "get_time_travel_debugger",
]
