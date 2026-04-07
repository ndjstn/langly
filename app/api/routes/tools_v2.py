"""Tool registry endpoints for v2 runtime."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.runtime.tools.base import Tool
from app.runtime.tools.service import get_tool_registry


router = APIRouter(prefix="/tools", tags=["tools-v2"])


class ToolSchema(BaseModel):
    """Serialized tool schema and metadata."""

    name: str
    description: str
    requires_approval: bool
    input_schema: dict
    output_schema: dict


class ToolListResponse(BaseModel):
    """List tools response."""

    tools: list[ToolSchema] = Field(default_factory=list)
    total: int


def _serialize_tool(tool: Tool) -> ToolSchema:
    return ToolSchema(
        name=tool.name,
        description=tool.description,
        requires_approval=tool.requires_approval,
        input_schema=tool.input_model.model_json_schema(),
        output_schema=tool.output_model.model_json_schema(),
    )


@router.get("/", response_model=ToolListResponse)
async def list_tools() -> ToolListResponse:
    registry = get_tool_registry()
    tools = [_serialize_tool(tool) for tool in registry.list_tools()]
    return ToolListResponse(tools=tools, total=len(tools))


@router.get("/{tool_name}", response_model=ToolSchema)
async def get_tool(tool_name: str) -> ToolSchema:
    registry = get_tool_registry()
    tool = registry.get(tool_name)
    if tool is None:
        raise HTTPException(status_code=404, detail="tool_not_found")
    return _serialize_tool(tool)
