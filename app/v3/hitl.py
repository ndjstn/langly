"""V3 human-in-the-loop approvals."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4


@dataclass
class ApprovalRequest:
    id: UUID = field(default_factory=uuid4)
    run_id: UUID | None = None
    prompt: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    resolved: bool = False


@dataclass
class ApprovalResponse:
    request_id: UUID
    approved: bool
    notes: str | None = None
    responded_at: datetime = field(default_factory=datetime.utcnow)


class HITLManager:
    def __init__(self) -> None:
        self._requests: dict[UUID, ApprovalRequest] = {}
        self._responses: dict[UUID, ApprovalResponse] = {}
        self._pending_tools: dict[UUID, dict[str, Any]] = {}

    def create_request(
        self,
        *,
        run_id: UUID | None,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> ApprovalRequest:
        request = ApprovalRequest(
            run_id=run_id,
            prompt=prompt,
            context=context or {},
        )
        self._requests[request.id] = request
        return request

    def resolve(self, response: ApprovalResponse) -> None:
        request = self._requests.get(response.request_id)
        if request:
            request.resolved = True
        self._responses[response.request_id] = response
        if response.request_id in self._pending_tools and not response.approved:
            self._pending_tools.pop(response.request_id, None)

    def list_requests(self, resolved: bool | None = None) -> list[ApprovalRequest]:
        if resolved is None:
            return list(self._requests.values())
        return [req for req in self._requests.values() if req.resolved == resolved]

    def register_pending_tool(
        self,
        *,
        request_id: UUID,
        tool_name: str,
        arguments: dict[str, Any],
        context: dict[str, Any],
    ) -> None:
        self._pending_tools[request_id] = {
            "tool_name": tool_name,
            "arguments": arguments,
            "context": context,
        }

    def pop_pending_tool(self, request_id: UUID) -> dict[str, Any] | None:
        return self._pending_tools.pop(request_id, None)


_hitl_manager: HITLManager | None = None


def get_hitl_manager() -> HITLManager:
    global _hitl_manager
    if _hitl_manager is None:
        _hitl_manager = HITLManager()
    return _hitl_manager
