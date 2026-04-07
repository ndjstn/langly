"""Memory summarization for v2 runtime."""
from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from app.runtime.llm import GraniteLLMProvider
from app.runtime.memory import BoundedMemory
from app.runtime.models import AgentRole


class MemorySummarizer:
    """Summarize older messages when memory is near capacity."""

    def __init__(self, provider: GraniteLLMProvider) -> None:
        self._provider = provider

    async def summarize(self, memory: BoundedMemory) -> str | None:
        if not memory.needs_summarization():
            return None

        if not memory.messages:
            return None

        cutoff = max(1, len(memory.messages) // 2)
        to_summarize = memory.messages[:cutoff]
        remaining = memory.messages[cutoff:]

        transcript = "\n".join(
            f"{msg.role.value}: {msg.content}" for msg in to_summarize
        )
        prompt = (
            "Summarize the following conversation snippets briefly, "
            "preserving key requirements and decisions:\n\n"
            f"{transcript}"
        )

        model = self._provider.get_model(AgentRole.PM)
        response = await model.ainvoke(
            [
                SystemMessage(content="You are a summarizer."),
                HumanMessage(content=prompt),
            ]
        )
        summary = str(getattr(response, "content", response))

        memory.summary = summary
        memory.messages = list(remaining)
        return summary
