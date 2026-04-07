"""HITL v2 endpoints for approvals."""
from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.runtime.hitl import ApprovalResponse, get_hitl_manager
from app.runtime.events import get_event_bus
from app.runtime.models import StateDelta, ToolCall, ToolCallStatus
from app.runtime.run_store import RunStore
from app.runtime.tools.base import ToolContext
from app.runtime.tools.service import get_tool_registry


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hitl", tags=["hitl-v2"])


class ApprovalRequestIn(BaseModel):
    """Create a new approval request."""

    run_id: UUID | None = None
    prompt: str = Field(..., min_length=1)
    context: dict[str, object] = Field(default_factory=dict)


class ApprovalRequestOut(BaseModel):
    """Approval request response."""

    id: UUID
    run_id: UUID | None = None
    prompt: str
    context: dict[str, object]
    created_at: datetime
    resolved: bool


class ApprovalResolveIn(BaseModel):
    """Resolve an approval request."""

    approved: bool
    notes: str | None = None


class ApprovalResolveOut(BaseModel):
    """Approval response."""

    request_id: UUID
    approved: bool
    notes: str | None = None
    responded_at: datetime
    tool_result: dict | None = None


class ApprovalListResponse(BaseModel):
    """List approvals response."""

    requests: list[ApprovalRequestOut]


class PendingToolsResponse(BaseModel):
    """Pending tool calls waiting for approval."""

    pending: list[dict]


@router.post("/requests", response_model=ApprovalRequestOut)
async def create_request(payload: ApprovalRequestIn) -> ApprovalRequestOut:
    manager = get_hitl_manager()
    request = manager.create_request(
        run_id=payload.run_id,
        prompt=payload.prompt,
        context=payload.context,
    )
    return ApprovalRequestOut(
        id=request.id,
        run_id=request.run_id,
        prompt=request.prompt,
        context=request.context,
        created_at=request.created_at,
        resolved=request.resolved,
    )


@router.get("/requests/{request_id}", response_model=ApprovalRequestOut)
async def get_request(request_id: UUID) -> ApprovalRequestOut:
    manager = get_hitl_manager()
    request = manager.get_request(request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="request_not_found")
    return ApprovalRequestOut(
        id=request.id,
        run_id=request.run_id,
        prompt=request.prompt,
        context=request.context,
        created_at=request.created_at,
        resolved=request.resolved,
    )


@router.get("/requests", response_model=ApprovalListResponse)
async def list_requests(resolved: bool | None = None) -> ApprovalListResponse:
    manager = get_hitl_manager()
    requests = manager.list_requests(resolved=resolved)
    return ApprovalListResponse(
        requests=[
            ApprovalRequestOut(
                id=req.id,
                run_id=req.run_id,
                prompt=req.prompt,
                context=req.context,
                created_at=req.created_at,
                resolved=req.resolved,
            )
            for req in requests
        ]
    )


@router.get("/pending-tools", response_model=PendingToolsResponse)
async def list_pending_tools() -> PendingToolsResponse:
    manager = get_hitl_manager()
    return PendingToolsResponse(pending=manager.list_pending_tools())


@router.post("/requests/{request_id}/resolve", response_model=ApprovalResolveOut)
async def resolve_request(
    request_id: UUID,
    payload: ApprovalResolveIn,
) -> ApprovalResolveOut:
    manager = get_hitl_manager()
    request = manager.get_request(request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="request_not_found")

    response = ApprovalResponse(
        request_id=request_id,
        approved=payload.approved,
        notes=payload.notes,
    )
    manager.resolve(response)

    if response.approved:
        pending = manager.pop_pending_tool(request_id)
        if pending:
            registry = get_tool_registry()
            context_payload = pending.get("context") or {}
            tool_context = ToolContext(
                session_id=context_payload.get("session_id", ""),
                run_id=context_payload.get("run_id", ""),
                actor=context_payload.get("actor", "pm"),
            )
            tool_output = await registry.execute(
                pending.get("tool_name", ""),
                pending.get("arguments", {}),
                tool_context,
                bypass_approval=True,
            )
            run_id_str = context_payload.get("run_id", "")
            try:
                run_id = UUID(run_id_str)
            except ValueError:
                run_id = None
            if run_id is not None:
                tool_call = ToolCall(
                    name=pending.get("tool_name", ""),
                    arguments=pending.get("arguments", {}),
                    status=ToolCallStatus.COMPLETED
                    if tool_output.success
                    else ToolCallStatus.FAILED,
                    result=tool_output.result,
                    error=tool_output.error,
                    metadata=tool_output.metadata,
                )
                delta = StateDelta(
                    run_id=run_id,
                    node="tool_approval_execute",
                    changes={"tool_calls": [tool_call]},
                )
                RunStore().save_delta(delta.model_dump())
                await get_event_bus().publish(
                    {
                        "type": "state_delta",
                        "delta": delta.model_dump(),
                    }
                )
            return ApprovalResolveOut(
                request_id=response.request_id,
                approved=response.approved,
                notes=response.notes,
                responded_at=response.responded_at,
                tool_result=tool_output.model_dump(),
            )

    return ApprovalResolveOut(
        request_id=response.request_id,
        approved=response.approved,
        notes=response.notes,
        responded_at=response.responded_at,
    )
