"""Workflow engine for Langly v2 runtime."""
from __future__ import annotations

import json
import logging
import traceback
from uuid import UUID, uuid4
from typing import Callable

from langchain_core.messages import SystemMessage

from app.core.constants import AGENT_SYSTEM_PROMPTS
from app.runtime.circuit_breaker import CircuitBreaker
from app.runtime.errors import ErrorKind, LanglyError
from app.runtime.events import get_event_bus
from app.runtime.llm import GraniteLLMProvider
from app.runtime.memory import BoundedMemory
from app.config import get_settings
from app.runtime.summarizer import MemorySummarizer
from app.runtime.models import (
    AgentRole,
    ErrorRecord,
    Message,
    MessageRole,
    RunStatus,
    Task,
    TaskStatus,
    ToolCall,
    ToolCallStatus,
    WorkflowRun,
    WorkflowState,
)
from app.runtime.router import Router
from app.runtime.neo4j_adapter import Neo4jMemoryAdapter
from app.runtime.snapshot_store import SnapshotStore
from app.runtime.state_store import InMemoryStateStore
from app.runtime.tools import ToolContext
from app.runtime.tools.service import get_tool_registry
from app.runtime.run_store import RunStore


logger = logging.getLogger(__name__)


class WorkflowEngine:
    """Minimal v2 workflow engine with PM + delegation."""

    _instance: "WorkflowEngine | None" = None

    def __init__(self) -> None:
        self._provider = GraniteLLMProvider()
        self._breaker = CircuitBreaker()
        self._memories: dict[UUID, BoundedMemory] = {}
        self._runs: dict[UUID, WorkflowRun] = {}
        self._router = Router(self._provider)
        self._store = InMemoryStateStore()
        self._tools = get_tool_registry()
        self._events = get_event_bus()
        self._summarizer = MemorySummarizer(self._provider)
        self._run_store = RunStore()
        self._snapshot_store = SnapshotStore()
        settings = get_settings()
        if settings.enable_neo4j_memory:
            self._neo4j = Neo4jMemoryAdapter()
        else:
            self._neo4j = None

    @classmethod
    def get_instance(cls) -> "WorkflowEngine":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _get_memory(self, session_id: UUID) -> BoundedMemory:
        if session_id not in self._memories:
            self._memories[session_id] = BoundedMemory()
        return self._memories[session_id]

    async def run(
        self,
        message: str,
        session_id: UUID | None = None,
        *,
        raise_on_error: bool = True,
        stream_callback: Callable[[dict[str, str]], None] | None = None,
        model_overrides: dict[str, str] | None = None,
    ) -> tuple[WorkflowRun, WorkflowState, str]:
        session_id = session_id or uuid4()
        run = WorkflowRun(
            session_id=session_id,
            status=RunStatus.RUNNING,
        )
        self._runs[run.id] = run
        self._run_store.save_run(run)

        memory = self._get_memory(session_id)
        base_state = self._store.get_state(session_id) or WorkflowState(
            session_id=session_id,
            status=TaskStatus.PENDING,
            current_agent=None,
            messages=list(memory.messages),
        )
        self._store.set_state(session_id, base_state)
        self._store.create_checkpoint(session_id, base_state)
        self._snapshot_store.save_snapshot(run.id, base_state)
        memory_snapshot = memory.snapshot()

        user_msg = Message(role=MessageRole.USER, content=message)
        memory.add(user_msg)
        state, delta = self._store.commit_delta(
            run_id=run.id,
            state=base_state,
            node="user_input",
            changes={
                "messages": list(memory.messages),
                "status": TaskStatus.IN_PROGRESS,
                "current_agent": AgentRole.PM,
            },
        )
        await self._publish_delta(delta)
        self._run_store.save_delta(delta.model_dump())
        self._snapshot_store.save_snapshot(run.id, state)
        state = await self._maybe_summarize(run, state, memory, session_id, stage="pre")

        if not self._breaker.can_execute():
            run.status = RunStatus.FAILED
            run.error = "circuit_breaker_open"
            error = LanglyError(
                "Circuit breaker open",
                kind=ErrorKind.TRANSIENT,
                retryable=True,
                details={"cooldown_seconds": self._breaker.cooldown_seconds},
            )
            record = ErrorRecord(
                kind=error.kind.value,
                message=str(error),
                retryable=error.retryable,
                node="circuit_breaker",
                details=error.details,
            )
            _, delta = self._store.commit_delta(
                run_id=run.id,
                state=state,
                node="circuit_breaker",
                changes={},
                errors=[record],
            )
            await self._publish_delta(delta)
            self._run_store.save_delta(delta.model_dump())
            self._snapshot_store.save_snapshot(run.id, state)
            self._store.rollback(session_id)
            memory.restore(memory_snapshot)
            raise error

        try:
            def emit_token(role: AgentRole, stage: str, token: str) -> None:
                if stream_callback is None:
                    return
                try:
                    stream_callback(
                        {
                            "role": role.value,
                            "stage": stage,
                            "token": token,
                        }
                    )
                except Exception:
                    return

            pm_response = await self._invoke_agent(
                AgentRole.PM,
                memory,
                model_override=(model_overrides or {}).get(AgentRole.PM.value),
                on_token=lambda token: emit_token(AgentRole.PM, "pm", token),
            )
            parsed = self._parse_pm_response(pm_response)

            response_text = parsed["response"]
            delegations = parsed.get("delegate_to") or []

            if delegations:
                tasks = self._build_tasks(delegations)
                state, delta = self._store.commit_delta(
                    run_id=run.id,
                    state=state,
                    node="pm_delegation",
                    changes={"tasks": tasks},
                )
                await self._publish_delta(delta)
                self._run_store.save_delta(delta.model_dump())
                self._snapshot_store.save_snapshot(run.id, state)
                outputs: list[str] = []

                for task in tasks:
                    assigned = task.assigned_agent
                    if assigned is None:
                        assigned = await self._router.route(task.description)
                        task.assigned_agent = assigned

                    task.status = TaskStatus.IN_PROGRESS
                    specialist_output = await self._invoke_agent(
                        assigned,
                        memory,
                        task_prompt=task.description,
                        model_override=(model_overrides or {}).get(assigned.value) if assigned else None,
                        on_token=lambda token, role=assigned: emit_token(role, "specialist", token),
                    )
                    task.result = specialist_output
                    task.status = TaskStatus.COMPLETED
                    outputs.append(
                        f"{assigned.value}: {specialist_output}"
                    )

                state, delta = self._store.commit_delta(
                    run_id=run.id,
                    state=state,
                    node="tasks_completed",
                    changes={"tasks": tasks},
                )
                await self._publish_delta(delta)
                self._run_store.save_delta(delta.model_dump())
                self._snapshot_store.save_snapshot(run.id, state)

                response_text = await self._synthesize_pm(
                    outputs,
                    memory,
                    model_override=(model_overrides or {}).get(AgentRole.PM.value),
                    on_token=lambda token: emit_token(AgentRole.PM, "synthesis", token),
                )

            tool_calls = self._extract_tool_calls(pm_response)
            if not tool_calls:
                tool_calls = self._extract_tool_calls(response_text)
            if tool_calls:
                executed_calls: list[ToolCall] = []
                for call in tool_calls:
                    executed_calls.append(
                        await self._execute_tool(
                            session_id=session_id,
                            run_id=run.id,
                            tool_name=call.get("name", ""),
                            arguments=call.get("arguments", {}),
                        )
                    )

                state, delta = self._store.commit_delta(
                    run_id=run.id,
                    state=state,
                    node="tool_calls",
                    changes={"tool_calls": executed_calls},
                )
                await self._publish_delta(delta)
                self._run_store.save_delta(delta.model_dump())
                self._snapshot_store.save_snapshot(run.id, state)

            assistant_msg = Message(
                role=MessageRole.ASSISTANT,
                content=response_text,
            )
            memory.add(assistant_msg)
            state, delta = self._store.commit_delta(
                run_id=run.id,
                state=state,
                node="assistant_response",
                changes={
                    "messages": list(memory.messages),
                    "status": TaskStatus.COMPLETED,
                    "current_agent": AgentRole.PM,
                },
            )
            await self._publish_delta(delta)
            self._run_store.save_delta(delta.model_dump())
            self._snapshot_store.save_snapshot(run.id, state)
            state = await self._maybe_summarize(run, state, memory, session_id, stage="post")

            summary = await self._summarizer.summarize(memory)
            if summary is not None:
                await self._maybe_persist_summary(session_id, summary)
                state, delta = self._store.commit_delta(
                    run_id=run.id,
                    state=state,
                    node="memory_summary",
                    changes={
                        "messages": list(memory.messages),
                        "summary": summary,
                    },
                )
                await self._publish_delta(delta)
                self._run_store.save_delta(delta.model_dump())
                self._snapshot_store.save_snapshot(run.id, state)

            run.status = RunStatus.COMPLETED
            run.result = {"response": response_text}
            self._run_store.update_run(run.id, run.status, run.result, None)

            return run, state, response_text

        except LanglyError as exc:
            record = ErrorRecord(
                kind=exc.kind.value,
                message=str(exc),
                retryable=exc.retryable,
                node="engine",
                details=exc.details,
            )
            _, delta = self._store.commit_delta(
                run_id=run.id,
                state=state,
                node="error",
                changes={},
                errors=[record],
            )
            await self._publish_delta(delta)
            self._run_store.save_delta(delta.model_dump())
            self._snapshot_store.save_snapshot(run.id, state)
            self._store.rollback(session_id)
            memory.restore(memory_snapshot)
            run.status = RunStatus.FAILED
            run.error = str(exc)
            self._run_store.update_run(run.id, run.status, None, run.error)
            if not raise_on_error:
                details = exc.details or {}
                response_text = (
                    "LLM invocation failed.\n\n"
                    f"Error: {exc}\n\n"
                    f"Details: {json.dumps(details, indent=2)}"
                )
                return run, state, response_text
            raise

    async def _invoke_agent(
        self,
        role: AgentRole,
        memory: BoundedMemory,
        *,
        task_prompt: str | None = None,
        model_override: str | None = None,
        on_token: Callable[[str], None] | None = None,
    ) -> str:
        system_prompt = AGENT_SYSTEM_PROMPTS.get(
            role.value,
            "You are a helpful assistant.",
        )
        messages = [SystemMessage(content=system_prompt)]
        messages.extend(memory.to_langchain_messages())

        if task_prompt:
            messages.append(SystemMessage(content=f"Task: {task_prompt}"))

        primary = self._provider.get_model(role, model_override=model_override)
        fallbacks = self._provider.get_fallback_models(role, model_override=model_override)
        candidates = [primary] + fallbacks
        last_error: Exception | None = None
        last_error_trace: str | None = None
        candidate_info: list[dict[str, str | None]] = []
        settings = get_settings()

        for candidate in candidates:
            try:
                candidate_info.append(
                    {
                        "model": getattr(candidate, "model", None),
                        "base_url": getattr(candidate, "base_url", None),
                    }
                )
                if on_token is not None:
                    collected = ""
                    try:
                        async for chunk in candidate.astream(messages):
                            piece = getattr(chunk, "content", None)
                            if piece is None:
                                piece = str(chunk)
                            if piece:
                                on_token(str(piece))
                                collected += str(piece)
                        self._breaker.record_success()
                        return collected
                    except Exception as stream_exc:
                        last_error = stream_exc
                        last_error_trace = traceback.format_exc()
                        self._breaker.record_failure()
                        logger.warning(
                            "%s model stream failed: %s (model=%s base_url=%s)",
                            role.value,
                            stream_exc,
                            getattr(candidate, "model", None),
                            getattr(candidate, "base_url", None),
                            exc_info=settings.debug,
                        )
                        continue

                response = await candidate.ainvoke(messages)
                self._breaker.record_success()
                return str(getattr(response, "content", response))
            except Exception as exc:
                last_error = exc
                last_error_trace = traceback.format_exc()
                self._breaker.record_failure()
                logger.warning(
                    "%s model failed: %s (model=%s base_url=%s)",
                    role.value,
                    exc,
                    getattr(candidate, "model", None),
                    getattr(candidate, "base_url", None),
                    exc_info=settings.debug,
                )

        raise LanglyError(
            f"{role.value} model invocation failed",
            kind=ErrorKind.RETRYABLE,
            retryable=True,
            details={
                "role": role.value,
                "ollama_host": self._provider._settings.ollama_host,
                "candidates": candidate_info,
                "error_type": type(last_error).__name__ if last_error else None,
                "error": str(last_error) if last_error else "unknown",
                "traceback": last_error_trace if settings.debug else None,
            },
        )

    def _parse_pm_response(self, content: str) -> dict[str, object]:
        result: dict[str, object] = {
            "response": content,
            "delegate_to": None,
        }

        if "```json" not in content:
            return result

        try:
            json_start = content.index("```json") + len("```json")
            json_end = content.index("```", json_start)
            json_str = content[json_start:json_end].strip()
            payload = json.loads(json_str)
            result["delegate_to"] = payload.get("delegate_to")
            result["response"] = content[:content.index("```json")].strip()
        except (ValueError, json.JSONDecodeError):
            return result

        return result

    def _extract_tool_calls(self, content: str) -> list[dict[str, object]]:
        if "```tools" not in content:
            return []

        try:
            start = content.index("```tools") + len("```tools")
            end = content.index("```", start)
            payload = content[start:end].strip()
            data = json.loads(payload)
            calls = data.get("tool_calls", [])
            if isinstance(calls, list):
                return [call for call in calls if isinstance(call, dict)]
        except (ValueError, json.JSONDecodeError):
            return []

        return []

    def _build_tasks(self, delegations: list[dict[str, str]]) -> list[Task]:
        tasks: list[Task] = []
        for delegation in delegations:
            agent_name = delegation.get("agent")
            description = delegation.get("task", "")
            assigned = self._map_agent(agent_name) if agent_name else None
            tasks.append(
                Task(
                    description=description,
                    assigned_agent=assigned,
                )
            )
        return tasks

    def _map_agent(self, name: str) -> AgentRole | None:
        mapping = {
            "pm": AgentRole.PM,
            "coder": AgentRole.CODER,
            "architect": AgentRole.ARCHITECT,
            "tester": AgentRole.TESTER,
            "reviewer": AgentRole.REVIEWER,
            "docs": AgentRole.DOCS,
            "router": AgentRole.ROUTER,
        }
        return mapping.get(name.lower())

    async def _maybe_summarize(
        self,
        run: WorkflowRun,
        state: WorkflowState,
        memory: BoundedMemory,
        session_id: UUID,
        *,
        stage: str,
    ) -> WorkflowState:
        if not memory.needs_summarization():
            return state
        summary = await self._summarizer.summarize(memory)
        if summary is None:
            return state
        await self._maybe_persist_summary(session_id, summary)
        state, delta = self._store.commit_delta(
            run_id=run.id,
            state=state,
            node=f"memory_summary_{stage}",
            changes={
                "messages": list(memory.messages),
                "summary": summary,
            },
        )
        await self._publish_delta(delta)
        self._run_store.save_delta(delta.model_dump())
        self._snapshot_store.save_snapshot(run.id, state)
        return state

    async def _synthesize_pm(
        self,
        outputs: list[str],
        memory: BoundedMemory,
        *,
        model_override: str | None = None,
        on_token: Callable[[str], None] | None = None,
    ) -> str:
        prompt = "\n\n".join(outputs)
        synthesis = (
            "Synthesize the following specialist outputs into a clear response:\n\n"
            f"{prompt}"
        )
        return await self._invoke_agent(
            AgentRole.PM,
            memory,
            task_prompt=synthesis,
            model_override=model_override,
            on_token=on_token,
        )

    async def _execute_tool(
        self,
        *,
        session_id: UUID,
        run_id: UUID,
        tool_name: str,
        arguments: dict[str, object],
    ) -> ToolCall:
        context = ToolContext(
            session_id=str(session_id),
            run_id=str(run_id),
            actor="pm",
        )
        output = await self._tools.execute(tool_name, arguments, context)
        return ToolCall(
            name=tool_name,
            arguments=arguments,
            status=ToolCallStatus.COMPLETED
            if output.success
            else ToolCallStatus.FAILED,
            result=output.result,
            error=output.error,
            metadata=output.metadata,
        )

    async def _publish_delta(self, delta: object) -> None:
        """Publish a delta event to subscribers."""
        try:
            payload = {
                "type": "state_delta",
                "delta": getattr(delta, "model_dump", lambda: delta)(),
            }
        except Exception:
            payload = {"type": "state_delta", "delta": str(delta)}
        await self._events.publish(payload)

    async def _maybe_persist_summary(self, session_id: UUID, summary: str) -> None:
        if self._neo4j is None:
            return
        try:
            await self._neo4j.store_summary(session_id, summary)
        except Exception:
            return
