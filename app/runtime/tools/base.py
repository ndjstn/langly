"""Tool interfaces for the v2 runtime."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ToolInput(BaseModel):
    """Base input model for tools."""

    pass


class ToolOutput(BaseModel):
    """Base output model for tools."""

    success: bool = True
    result: Any | None = None
    error: str | None = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


@dataclass
class ToolContext:
    """Context passed to tool execution."""

    session_id: str
    run_id: str
    actor: str


class Tool(ABC):
    """Abstract tool interface."""

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @property
    def requires_approval(self) -> bool:
        return False

    @property
    def description(self) -> str:
        return ""

    @property
    def input_model(self) -> type[ToolInput]:
        return ToolInput

    @property
    def output_model(self) -> type[ToolOutput]:
        return ToolOutput

    async def validate(self, _input: ToolInput) -> list[str]:
        return []

    @abstractmethod
    async def run(self, _input: ToolInput, _context: ToolContext) -> ToolOutput:
        raise NotImplementedError
