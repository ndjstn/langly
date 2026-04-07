"""Bounded memory store with pruning and summary placeholder."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.runtime.models import Message, MessageRole


@dataclass
class BoundedMemory:
    """In-memory bounded conversation store with pruning."""

    max_messages: int = 200
    summarize_threshold: float = 0.8
    messages: list[Message] = field(default_factory=list)
    summary: str | None = None

    def add(self, message: Message) -> None:
        """Add a message and prune if needed."""
        self.messages.append(message)
        self._prune_if_needed()

    def extend(self, messages: Iterable[Message]) -> None:
        """Add multiple messages and prune if needed."""
        self.messages.extend(messages)
        self._prune_if_needed()

    def _prune_if_needed(self) -> None:
        """Prune oldest messages when exceeding max_messages."""
        if self.max_messages <= 0:
            return

        if len(self.messages) <= self.max_messages:
            return

        excess = len(self.messages) - self.max_messages
        removed = self.messages[:excess]
        self.messages = self.messages[excess:]

        removed_count = len(removed)
        note = f"[pruned {removed_count} messages]"
        if self.summary:
            self.summary = f"{self.summary}\n{note}"
        else:
            self.summary = note

    def needs_summarization(self) -> bool:
        """Return True if memory is near capacity."""
        if self.max_messages <= 0:
            return False
        return len(self.messages) >= int(self.max_messages * self.summarize_threshold)

    def snapshot(self) -> dict[str, object]:
        """Capture a snapshot of the memory state."""
        return {
            "messages": list(self.messages),
            "summary": self.summary,
        }

    def restore(self, snapshot: dict[str, object]) -> None:
        """Restore memory from a snapshot."""
        messages = snapshot.get("messages", [])
        self.messages = list(messages) if isinstance(messages, list) else []
        summary = snapshot.get("summary")
        self.summary = str(summary) if summary is not None else None

    def to_langchain_messages(self) -> list[SystemMessage | HumanMessage | AIMessage]:
        """Convert stored messages into LangChain message objects."""
        lc_messages: list[SystemMessage | HumanMessage | AIMessage] = []

        if self.summary:
            lc_messages.append(SystemMessage(content=f"Summary: {self.summary}"))

        for msg in self.messages:
            if msg.role == MessageRole.USER:
                lc_messages.append(HumanMessage(content=msg.content))
            elif msg.role == MessageRole.ASSISTANT:
                lc_messages.append(AIMessage(content=msg.content))
            elif msg.role == MessageRole.SYSTEM:
                lc_messages.append(SystemMessage(content=msg.content))

        return lc_messages
