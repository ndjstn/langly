"""Tool registry bootstrap for V3."""
from __future__ import annotations

from app.v3.tools.builtin import ApprovalRequiredTool, EchoTool
from app.v3.tools.registry import ToolRegistry


_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        registry = ToolRegistry()
        registry.register(EchoTool())
        registry.register(ApprovalRequiredTool())
        _registry = registry
    return _registry
