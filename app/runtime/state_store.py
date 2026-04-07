"""In-memory state store with transactional delta commits."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from app.runtime.models import ErrorRecord, StateDelta, WorkflowState


@dataclass
class InMemoryStateStore:
    """Minimal in-memory state store with checkpointing."""

    states: dict[UUID, WorkflowState] = field(default_factory=dict)
    deltas: dict[UUID, list[StateDelta]] = field(default_factory=dict)
    checkpoints: dict[UUID, list[WorkflowState]] = field(default_factory=dict)

    def get_state(self, session_id: UUID) -> WorkflowState | None:
        return self.states.get(session_id)

    def set_state(self, session_id: UUID, state: WorkflowState) -> None:
        self.states[session_id] = state

    def create_checkpoint(self, session_id: UUID, state: WorkflowState) -> None:
        self.checkpoints.setdefault(session_id, []).append(state.model_copy(deep=True))

    def rollback(self, session_id: UUID) -> WorkflowState | None:
        stack = self.checkpoints.get(session_id)
        if not stack:
            return None
        restored = stack[-1].model_copy(deep=True)
        self.states[session_id] = restored
        return restored

    def commit_delta(
        self,
        *,
        run_id: UUID,
        state: WorkflowState,
        node: str,
        changes: dict[str, Any],
        errors: list[ErrorRecord] | None = None,
    ) -> tuple[WorkflowState, StateDelta]:
        delta = StateDelta(
            run_id=run_id,
            node=node,
            changes=changes,
            errors=errors or [],
        )
        new_state = state.model_copy(update=changes)
        new_state.updated_at = datetime.utcnow()
        self.set_state(state.session_id, new_state)
        self.deltas.setdefault(run_id, []).append(delta)
        return new_state, delta
