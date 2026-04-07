"""Guardian gate for tool execution."""
from __future__ import annotations

from typing import Any

try:
    from app.llm.guardian import validate_before_execution
except Exception:  # pragma: no cover - optional dependency
    validate_before_execution = None


async def guard_tool_call(name: str, arguments: dict[str, Any]) -> tuple[bool, str | None]:
    """Return (allowed, reason) for a tool call."""
    if validate_before_execution is None:
        return True, None

    payload = f"Tool: {name}\nArguments: {arguments}"
    result = await validate_before_execution(payload)

    if not result.is_safe:
        return False, result.summary

    return True, None
