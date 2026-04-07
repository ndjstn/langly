"""Tool interfaces for V3."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ToolInput(BaseModel):
    pass


class ToolOutput(BaseModel):
    success: bool = True
    result: Any | None = None
    error: str | None = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


@dataclass
class ToolContext:
    session_id: str | None
    run_id: str | None
    actor: str = "system"


class Tool(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @property
    def description(self) -> str:
        return ""

    @property
    def input_model(self) -> type[ToolInput]:
        return ToolInput

    @property
    def requires_approval(self) -> bool:
        return False

    async def validate(self, _input: ToolInput) -> list[str]:
        return []

    @abstractmethod
    async def run(self, _input: ToolInput, _context: ToolContext) -> ToolOutput:
        raise NotImplementedError
