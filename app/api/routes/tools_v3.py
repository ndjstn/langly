"""V3 tool endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.v3.tools import get_tool_registry
from app.v3.tools.base import ToolContext


router = APIRouter()


class ToolCallRequest(BaseModel):
    name: str
    arguments: dict = {}
    session_id: UUID | None = None
    run_id: UUID | None = None
    actor: str = "api"


@router.get("/tools")
async def list_tools() -> dict[str, list[dict[str, object]]]:
    registry = get_tool_registry()
    tools = [
        {
            "name": tool.name,
            "description": tool.description,
            "requires_approval": tool.requires_approval,
        }
        for tool in registry.list_tools()
    ]
    return {"tools": tools}


@router.post("/tools/call")
async def call_tool(payload: ToolCallRequest) -> dict[str, object]:
    registry = get_tool_registry()
    tool = registry.get(payload.name)
    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")

    context = ToolContext(
        session_id=str(payload.session_id) if payload.session_id else None,
        run_id=str(payload.run_id) if payload.run_id else None,
        actor=payload.actor,
    )
    output = await registry.execute(payload.name, payload.arguments, context)
    return output.model_dump()
