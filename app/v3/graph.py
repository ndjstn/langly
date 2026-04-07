"""Graph execution primitives for V3."""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.v3.models import StateDelta, Task, ToolCall


class NodeContext(BaseModel):
    run_id: UUID
    session_id: UUID
    state: dict[str, Any] = Field(default_factory=dict)


class NodeResult(BaseModel):
    output: str | None = None
    deltas: list[StateDelta] = Field(default_factory=list)
    tasks: list[Task] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)


class GraphNode(ABC):
    """Stateless graph node interface."""

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def run(self, context: NodeContext, input_text: str) -> NodeResult:
        raise NotImplementedError


class GraphExecutor:
    """Minimal graph executor (sequential with parallel hooks)."""

    def __init__(self, nodes: list[GraphNode]) -> None:
        self._nodes = nodes

    async def run(self, context: NodeContext, input_text: str) -> NodeResult:
        current = input_text
        aggregated = NodeResult()

        for node in self._nodes:
            result = await node.run(context, current)
            if result.output is not None:
                current = result.output
            aggregated.deltas.extend(result.deltas)
            aggregated.tasks.extend(result.tasks)
            aggregated.tool_calls.extend(result.tool_calls)

        aggregated.output = current
        return aggregated

    async def run_parallel(
        self,
        context: NodeContext,
        inputs: list[str],
        node: GraphNode,
        concurrency: int = 4,
    ) -> list[NodeResult]:
        """Execute a node over inputs in parallel with a cap."""
        semaphore = asyncio.Semaphore(concurrency)

        async def _run(item: str) -> NodeResult:
            async with semaphore:
                return await node.run(context, item)

        return await asyncio.gather(*[_run(item) for item in inputs])
