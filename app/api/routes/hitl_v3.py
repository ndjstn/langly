"""V3 human-in-the-loop endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.v3.hitl import ApprovalResponse, get_hitl_manager
from app.v3.runtime import get_engine
from app.v3.tools.base import ToolContext


router = APIRouter()


class ApprovalResolveRequest(BaseModel):
    approved: bool
    notes: str | None = None


@router.get("/hitl/requests")
async def list_requests(resolved: bool | None = None) -> dict[str, list[dict[str, object]]]:
    manager = get_hitl_manager()
    requests = [
        {
            "id": str(req.id),
            "run_id": str(req.run_id) if req.run_id else None,
            "prompt": req.prompt,
            "context": req.context,
            "created_at": req.created_at.isoformat(),
            "resolved": req.resolved,
        }
        for req in manager.list_requests(resolved)
    ]
    return {"requests": requests}


@router.post("/hitl/requests/{request_id}/resolve")
async def resolve_request(
    request_id: UUID,
    payload: ApprovalResolveRequest,
) -> dict[str, object]:
    manager = get_hitl_manager()
    requests = manager.list_requests()
    if request_id not in {req.id for req in requests}:
        raise HTTPException(status_code=404, detail="Request not found")

    response = ApprovalResponse(
        request_id=request_id,
        approved=payload.approved,
        notes=payload.notes,
    )
    manager.resolve(response)
    resumed = False
    if payload.approved:
        pending = manager.pop_pending_tool(request_id)
        if pending:
            engine = get_engine()
            context = pending.get("context") or {}
            tool_ctx = ToolContext(
                session_id=context.get("session_id"),
                run_id=context.get("run_id"),
                actor=context.get("actor", "hitl"),
            )
            output = await engine._tools.execute(
                pending.get("tool_name", ""),
                pending.get("arguments", {}),
                tool_ctx,
            )
            resumed = output.success
    return {
        "request_id": str(request_id),
        "approved": payload.approved,
        "notes": payload.notes,
        "resumed": resumed,
    }
