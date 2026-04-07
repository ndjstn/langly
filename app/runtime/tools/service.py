"""Singleton tool registry service."""
from __future__ import annotations

from app.runtime.tools.builtin import EchoTool
from app.runtime.tools.approval_tool import ApprovalRequiredTool
from app.runtime.tools.registry import ToolRegistry


_tool_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """Return a singleton ToolRegistry with builtins registered."""
    global _tool_registry
    if _tool_registry is None:
        registry = ToolRegistry()
        registry.register(EchoTool())
        registry.register(ApprovalRequiredTool())
        _tool_registry = registry
    return _tool_registry
