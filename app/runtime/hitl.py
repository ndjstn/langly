"""Human-in-the-loop scaffolding for v2 runtime."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4


@dataclass
class ApprovalRequest:
    """Request for human approval."""

    id: UUID = field(default_factory=uuid4)
    run_id: UUID | None = None
    prompt: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    resolved: bool = False


@dataclass
class ApprovalResponse:
    """Response from human approval."""

    request_id: UUID
    approved: bool
    notes: str | None = None
    responded_at: datetime = field(default_factory=datetime.utcnow)


class HITLManager:
    """In-memory HITL manager for approvals."""

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

    def get_request(self, request_id: UUID) -> ApprovalRequest | None:
        return self._requests.get(request_id)

    def get_response(self, request_id: UUID) -> ApprovalResponse | None:
        return self._responses.get(request_id)

    def list_requests(self, resolved: bool | None = None) -> list[ApprovalRequest]:
        if resolved is None:
            return list(self._requests.values())
        return [req for req in self._requests.values() if req.resolved == resolved]

    def list_pending_tools(self) -> list[dict[str, Any]]:
        return [
            {"request_id": str(req_id), **payload}
            for req_id, payload in self._pending_tools.items()
        ]

    def register_pending_tool(
        self,
        *,
        request_id: UUID,
        tool_name: str,
        arguments: dict[str, Any],
        context: Any,
    ) -> None:
        context_payload = context
        if hasattr(context, "session_id"):
            context_payload = {
                "session_id": getattr(context, "session_id"),
                "run_id": getattr(context, "run_id"),
                "actor": getattr(context, "actor"),
            }
        self._pending_tools[request_id] = {
            "tool_name": tool_name,
            "arguments": arguments,
            "context": context_payload,
        }

    def pop_pending_tool(self, request_id: UUID) -> dict[str, Any] | None:
        return self._pending_tools.pop(request_id, None)

    def clear_for_runs(self, run_ids: list[str]) -> int:
        if not run_ids:
            return 0
        run_id_set = {str(run_id) for run_id in run_ids}
        to_remove: list[UUID] = []
        for req_id, request in self._requests.items():
            if request.run_id is not None and str(request.run_id) in run_id_set:
                to_remove.append(req_id)
        for req_id in list(self._pending_tools.keys()):
            payload = self._pending_tools.get(req_id) or {}
            context = payload.get("context") or {}
            if str(context.get("run_id")) in run_id_set:
                to_remove.append(req_id)
        cleared = 0
        for req_id in set(to_remove):
            if req_id in self._requests:
                self._requests.pop(req_id, None)
                cleared += 1
            self._responses.pop(req_id, None)
            self._pending_tools.pop(req_id, None)
        return cleared


_hitl_manager: HITLManager | None = None


def get_hitl_manager() -> HITLManager:
    """Get a singleton HITL manager."""
    global _hitl_manager
    if _hitl_manager is None:
        _hitl_manager = HITLManager()
    return _hitl_manager
