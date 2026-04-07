"""Scope-aware harness endpoint for v2 runtime."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import traceback
from uuid import UUID
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

from app.config import get_settings
from app.harness import (
    ABTestResult,
    ABTester,
    AutoToolRunner,
    GradeResult,
    ResponseGrader,
    RecoveryAdvice,
    RecoveryPlanner,
    HarnessStatusEmitter,
    IterationPlanner,
    HarnessTuner,
    PostprocessResult,
    PromptEnhancer,
    PromptEnhancement,
    ResearchResult,
    ResearchPolicy,
    ToolResult,
    ToolReconfigurator,
    ModelRoutingDecision,
    ModelRoutingPolicy,
    ToolSelectionDecision,
    ToolSelectionPolicy,
    TuningSummary,
    TuningState,
    TaskCapture,
    TaskCaptureResult,
    TaskCandidate,
    TaskTemplate,
    TaskTemplateEngine,
    TaskTemplateResult,
    KataEngine,
    KataPlan,
    KataPhase,
    get_harness_cache,
    Scope,
    ScopeClassifier,
    TraceBuilder,
    build_mermaid_graph,
)
from app.harness.research import SearxClient
from app.harness.postprocess import ResponsePostProcessor
from app.runtime import RunStatus, WorkflowEngine
from app.runtime.events import get_event_bus
from app.runtime.models import StateDelta
from app.runtime.run_store import RunStore
from app.runtime.tools.base import Tool
from app.runtime.tools.service import get_tool_registry


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/harness", tags=["harness-v2"])


class ToolSchema(BaseModel):
    name: str
    description: str
    requires_approval: bool
    input_schema: dict
    output_schema: dict


class HarnessRunRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: UUID | None = None
    mode: str | None = None
    scope: Scope | None = None
    auto_tools: list[str] | None = None
    iterations: int | None = Field(default=None, ge=1, le=5)
    request_id: str | None = None
    ab_test: bool | None = None
    grade: bool | None = None
    research: bool | None = None
    research_query: str | None = None
    prompt_enhance: bool | None = None
    citations: bool | None = None
    tool_selection: bool | None = None
    tuning: bool | None = None
    force: bool | None = None
    current_date: str | None = None
    cutoff_date: str | None = None
    task_capture: bool | None = None
    task_capture_commit: bool | None = None
    task_templates: bool | None = None


class ToolResultOut(BaseModel):
    name: str
    status: str
    output: object | None = None
    stdout: str | None = None
    stderr: str | None = None
    attempts: int = 1
    retries: int = 0
    cached: bool = False
    duration_ms: float


class ResearchSourceOut(BaseModel):
    title: str
    url: str
    snippet: str | None = None
    score: float | None = None


class ResearchOut(BaseModel):
    query: str
    sources: list[ResearchSourceOut]
    used: bool
    error: str | None = None
    duration_ms: float | None = None


class PromptEnhancementOut(BaseModel):
    applied: list[str]
    notes: list[str]
    citations_required: bool
    current_date: str
    cutoff_date: str
    sources: list[ResearchSourceOut]


class PostprocessOut(BaseModel):
    citations_added: bool
    warnings: list[str]


class ToolSelectionOut(BaseModel):
    selected_tools: list[str]
    excluded_tools: list[str]
    reason: str


class TuningActionOut(BaseModel):
    kind: str
    detail: dict[str, object]


class TuningOut(BaseModel):
    actions: list[TuningActionOut]
    notes: list[str]


class TuningStateOut(BaseModel):
    iterations: int | None = None
    auto_tools: list[str] | None = None
    research: bool | None = None
    prompt_enhance: bool | None = None
    citations: bool | None = None


class TaskCandidateOut(BaseModel):
    description: str
    source: str
    tags: list[str]


class TaskCaptureOut(BaseModel):
    candidates: list[TaskCandidateOut]
    created: list[str]
    skipped: list[str]
    error: str | None = None


class TaskTemplateOut(BaseModel):
    name: str
    checklist: list[str]


class TaskTemplateResultOut(BaseModel):
    templates: list[TaskTemplateOut]
    reason: str


class KataPhaseOut(BaseModel):
    name: str
    steps: list[str]


class KataPlanOut(BaseModel):
    intent: str
    phases: list[KataPhaseOut]


class HarnessBatchRequest(BaseModel):
    messages: list[str] = Field(..., min_length=1, max_length=10)
    mode: str | None = None
    auto_tools: list[str] | None = None
    iterations: int | None = Field(default=None, ge=1, le=5)
    request_id: str | None = None
    ab_test: bool | None = None
    grade: bool | None = None
    research: bool | None = None
    research_query: str | None = None
    prompt_enhance: bool | None = None
    citations: bool | None = None
    tool_selection: bool | None = None
    tuning: bool | None = None
    task_capture: bool | None = None
    task_capture_commit: bool | None = None
    task_templates: bool | None = None


class HarnessBatchResponse(BaseModel):
    batch_id: str
    runs: list[HarnessRunResponse]
    tuning_actions: list[list[TuningActionOut]]
    final_state: TuningStateOut | None = None


class TraceOut(BaseModel):
    why: str
    how: str
    suggestions: str
    hindsight: str
    foresight: str


class TaskWarriorOut(BaseModel):
    summary: dict[str, int]
    count: int
    tasks: list[dict[str, object]]


class ToolReconfigOut(BaseModel):
    disabled_tools: list[str]
    retry_overrides: dict[str, int]
    notes: list[str]
    rerun: bool = False


class IterationOut(BaseModel):
    index: int
    run_id: UUID
    status: RunStatus
    response: str


class HarnessRunResponse(BaseModel):
    run_id: UUID
    session_id: UUID
    request_id: str
    status: RunStatus
    response: str
    scope: Scope
    available_tools: list[ToolSchema]
    tools_used: list[ToolResultOut]
    tool_selection: ToolSelectionOut | None = None
    taskwarrior: TaskWarriorOut | None = None
    tool_reconfig: ToolReconfigOut | None = None
    research: ResearchOut | None = None
    prompt_enhancement: PromptEnhancementOut | None = None
    postprocess: PostprocessOut | None = None
    task_capture: TaskCaptureOut | None = None
    task_templates: TaskTemplateResultOut | None = None
    katas: KataPlanOut | None = None
    iterations: list[IterationOut] = []
    iterations_used: int = 1
    iterations_auto: bool = False
    ab_test: ABTestResult | None = None
    grade: GradeResult | None = None
    model_routing: ModelRoutingDecision | None = None
    recovery: RecoveryAdvice | None = None
    tuning: TuningOut | None = None
    trace: TraceOut
    mermaid: str
    timings: dict[str, float] = {}
    cached: bool = False


def _serialize_tool(tool: Tool) -> ToolSchema:
    return ToolSchema(
        name=tool.name,
        description=tool.description,
        requires_approval=tool.requires_approval,
        input_schema=tool.input_model.model_json_schema(),
        output_schema=tool.output_model.model_json_schema(),
    )


def _build_context(
    scope: Scope,
    tools: list[ToolSchema],
    tool_results: list[ToolResultOut],
    recovery: RecoveryAdvice | None = None,
    tool_reconfig: ToolReconfigOut | None = None,
    model_routing: ModelRoutingDecision | None = None,
    research: ResearchResult | None = None,
    tool_selection: ToolSelectionDecision | None = None,
) -> str:
    tool_names = [tool.name for tool in tools]
    serialized_tools = [
        {
            "name": tool.name,
            "requires_approval": tool.requires_approval,
            "input_schema": tool.input_schema,
        }
        for tool in tools
    ]
    tool_outputs = [
        {
            "name": tool.name,
            "status": tool.status,
            "output": tool.output,
            "stdout": (tool.stdout or "")[:2000],
            "stderr": (tool.stderr or "")[:2000],
            "attempts": tool.attempts,
            "retries": tool.retries,
            "cached": tool.cached,
        }
        for tool in tool_results
    ]
    payload = {
        "scope": scope.model_dump(),
        "available_tool_names": tool_names,
        "available_tools": serialized_tools,
        "auto_tool_names": [tool.name for tool in tool_results],
        "auto_tool_results": tool_outputs,
        "recovery": recovery.model_dump() if recovery else None,
        "tool_reconfig": tool_reconfig.model_dump() if tool_reconfig else None,
        "model_routing": model_routing.model_dump() if model_routing else None,
        "research": research.model_dump() if research else None,
        "tool_selection": tool_selection.model_dump() if tool_selection else None,
    }
    return json.dumps(jsonable_encoder(payload), ensure_ascii=False)


@router.post("/run", response_model=HarnessRunResponse)
async def run_harness(payload: HarnessRunRequest) -> HarnessRunResponse:
    request_id = payload.request_id or str(uuid4())
    start_total = time.perf_counter()
    cache = get_harness_cache(
        max_entries=int(os.getenv("LANGLY_CACHE_MAX", "128")),
        ttl_seconds=int(os.getenv("LANGLY_CACHE_TTL_SEC", "60")),
    )
    cache_key = json.dumps(
        {
            "message": payload.message,
            "mode": payload.mode,
            "auto_tools": payload.auto_tools,
            "iterations": payload.iterations,
            "ab_test": payload.ab_test,
            "grade": payload.grade,
            "research": payload.research,
            "research_query": payload.research_query,
            "prompt_enhance": payload.prompt_enhance,
            "citations": payload.citations,
            "tool_selection": payload.tool_selection,
            "tuning": payload.tuning,
            "current_date": payload.current_date,
            "cutoff_date": payload.cutoff_date,
            "task_capture": payload.task_capture,
            "task_capture_commit": payload.task_capture_commit,
            "task_templates": payload.task_templates,
        },
        sort_keys=True,
    )
    cached = None if payload.force else cache.get(cache_key)
    classifier = ScopeClassifier()
    scope_start = time.perf_counter()
    scope = payload.scope or await classifier.classify(payload.message)
    scope_ms = (time.perf_counter() - scope_start) * 1000
    if payload.mode in {"doing", "knowing"}:
        scope = scope.model_copy(update={"mode": payload.mode})

    registry = get_tool_registry()
    available_tools = [_serialize_tool(tool) for tool in registry.list_tools()]

    runner = AutoToolRunner()
    if payload.auto_tools is not None:
        runner.auto_tools = payload.auto_tools
    tool_selection: ToolSelectionDecision | None = None
    selection_enabled = (
        payload.tool_selection
        if payload.tool_selection is not None
        else os.getenv("LANGLY_TOOL_SELECTION_ENABLED", "true").lower() == "true"
    )
    if selection_enabled:
        policy = ToolSelectionPolicy()
        tool_selection = policy.select(
            payload.message,
            scope.model_dump(),
            available=runner.registry.names(),
            defaults=runner.auto_tools,
        )
        runner.auto_tools = tool_selection.selected_tools

    engine = WorkflowEngine.get_instance()
    tool_results_out: list[ToolResultOut] = []
    context: str | None = None
    taskwarrior: TaskWarriorOut | None = None
    recovery: RecoveryAdvice | None = None
    research: ResearchResult | None = None
    prompt_enhancement: PromptEnhancement | None = None
    postprocess: PostprocessResult | None = None
    tuning: TuningSummary | None = None
    iteration_outputs: list[IterationOut] = []
    iterations_auto = False
    iterations_used = 1
    ab_test: ABTestResult | None = None
    grade: GradeResult | None = None
    tool_reconfig: ToolReconfigOut | None = None
    model_routing: ModelRoutingDecision | None = None
    timings: dict[str, float] = {}
    task_capture_result: TaskCaptureResult | None = None
    task_templates_result: TaskTemplateResult | None = None
    kata_plan: KataPlan | None = None
    bus = get_event_bus()
    emitter = HarnessStatusEmitter(
        bus=bus,
        request_id=request_id,
        loop=asyncio.get_running_loop(),
    )
    if cached:
        await emitter.emit(
            "cache",
            "hit",
            detail={"request_id": request_id},
            progress=1.0,
        )
        cached_response = dict(cached)
        cached_response["request_id"] = request_id
        cached_response["cached"] = True
        return HarnessRunResponse(**cached_response)
    await emitter.emit(
        "scope",
        "done",
        detail={"mode": scope.mode, "intent": scope.intent, "difficulty": scope.difficulty},
        progress=0.05,
    )
    kata_plan = KataEngine().plan(scope.model_dump())
    await emitter.emit(
        "kata_before",
        "done",
        detail={"steps": kata_plan.phases[0].steps},
        progress=0.06,
    )

    try:
        await emitter.emit("tools", "start", progress=0.1)
        tools_start = time.perf_counter()
        def _tool_observer(phase: str, name: str, result: ToolResult | None) -> None:
            if phase == "start":
                emitter.emit_sync(
                    "tool_start",
                    "running",
                    detail={"name": name},
                )
                return
            if result is None:
                return
            emitter.emit_sync(
                "tool_done",
                result.status,
                detail={
                    "name": result.name,
                    "status": result.status,
                    "stderr": (result.stderr or "")[:500],
                    "stdout": (result.stdout or "")[:500],
                    "attempts": result.attempts,
                    "retries": result.retries,
                },
            )

        tool_results = await runner.run(
            payload.message,
            scope.model_dump(),
            observer=_tool_observer,
        )
        tools_ms = (time.perf_counter() - tools_start) * 1000
        timings["tools_ms"] = tools_ms
        await emitter.emit(
            "kata_during",
            "done",
            detail={"steps": kata_plan.phases[1].steps if kata_plan else []},
            progress=0.17,
        )
        tool_results_out = [ToolResultOut(**tool.model_dump()) for tool in tool_results]
        for tool in tool_results_out:
            if tool.name == "taskwarrior" and tool.status == "ok" and isinstance(tool.output, dict):
                output = tool.output
                if {"summary", "tasks"} <= output.keys():
                    taskwarrior = TaskWarriorOut(
                        summary=output.get("summary", {}),
                        count=int(output.get("count", 0)),
                        tasks=output.get("tasks", []),
                    )
                break
        if any(tool.status == "error" for tool in tool_results_out):
            await emitter.emit("recovery", "start")
            recovery = await RecoveryPlanner().build(
                payload.message,
                scope.model_dump(),
                [tool.model_dump() for tool in tool_results_out],
            )
            await emitter.emit("recovery", "done")
        if recovery is not None:
            reconfig = ToolReconfigurator().plan(
                [tool.model_dump() for tool in tool_results_out],
                recovery.model_dump(),
            )
            if reconfig.changed:
                rerun = os.getenv("LANGLY_TOOL_RECOVERY_RERUN", "true").lower() == "true"
                tool_reconfig = ToolReconfigOut(
                    disabled_tools=reconfig.disabled_tools,
                    retry_overrides=reconfig.retry_overrides,
                    notes=reconfig.notes,
                    rerun=rerun,
                )
                runner.apply_reconfiguration(
                    disabled_tools=reconfig.disabled_tools,
                    retry_overrides=reconfig.retry_overrides,
                )
                if rerun:
                    await emitter.emit("tools_rerun", "start", progress=0.15)
                    rerun_results = await runner.run(
                        payload.message,
                        scope.model_dump(),
                        observer=_tool_observer,
                    )
                    tool_results_out.extend([ToolResultOut(**tool.model_dump()) for tool in rerun_results])
                    await emitter.emit("tools_rerun", "done", progress=0.18)

        model_routing = ModelRoutingPolicy().plan(scope.model_dump())
        await emitter.emit(
            "model_routing",
            "done",
            detail={"overrides": model_routing.overrides, "reason": model_routing.reason},
            progress=0.2,
        )

        citations_required = (
            payload.citations
            if payload.citations is not None
            else os.getenv("LANGLY_CITATIONS_DEFAULT", "false").lower() == "true"
        )
        research_enabled = (
            payload.research
            if payload.research is not None
            else os.getenv("LANGLY_RESEARCH_DEFAULT", "false").lower() == "true"
        )
        if citations_required and not research_enabled:
            research_enabled = True
        research_plan = ResearchPolicy().plan(
            payload.message,
            scope.model_dump(),
            requested=research_enabled,
            query_override=payload.research_query,
        )
        if research_plan.enabled:
            await emitter.emit("research", "start", progress=0.19)
            research = await SearxClient().search(
                research_plan.query,
                limit=int(os.getenv("LANGLY_SEARX_LIMIT", "5")),
            )
            if research and research.duration_ms is not None:
                timings["research_ms"] = research.duration_ms
            await emitter.emit(
                "research",
                "done",
                detail={
                    "query": research_plan.query,
                    "sources": len(research.sources) if research else 0,
                    "error": research.error if research else None,
                },
                progress=0.21,
            )

        context = _build_context(
            scope,
            available_tools,
            tool_results_out,
            recovery,
            tool_reconfig,
            model_routing,
            research,
            tool_selection,
        )

        planner = IterationPlanner(max_iterations=int(os.getenv("LANGLY_ITERATION_MAX", "3")))
        plan = planner.plan(
            scope=scope.model_dump(),
            tool_results=[tool.model_dump() for tool in tool_results_out],
            requested=payload.iterations if payload.iterations is not None else None,
        )
        iterations = plan.iterations
        iterations_auto = plan.auto
        iterations_used = iterations
        await emitter.emit(
            "iterations_plan",
            "done",
            detail={"iterations": iterations, "auto": plan.auto, "reason": plan.reason},
            progress=0.22,
        )

        response_text = ""
        run = None
        session_id = payload.session_id
        current_message = payload.message
        iterations_start = time.perf_counter()
        budget_ms = int(os.getenv("LANGLY_ITERATION_BUDGET_MS", "0"))
        similarity_stop = float(os.getenv("LANGLY_ITERATION_SIMILARITY_STOP", "0.96"))
        prev_response = ""
        prompt_enhance_enabled = (
            payload.prompt_enhance
            if payload.prompt_enhance is not None
            else os.getenv("LANGLY_PROMPT_ENHANCE_DEFAULT", "true").lower() == "true"
        )
        enhancer = PromptEnhancer()

        token_buffer: list[str] = []
        last_flush = time.monotonic()
        min_chars = int(os.getenv("LANGLY_STREAM_MIN_CHARS", "24"))
        flush_ms = int(os.getenv("LANGLY_STREAM_FLUSH_MS", "120"))

        def flush_tokens(iteration: int | None = None) -> None:
            nonlocal last_flush
            if not token_buffer:
                return
            emitter.emit_token_sync(
                token="".join(token_buffer),
                role="pm",
                stage="pm",
                iteration=iteration,
            )
            token_buffer.clear()
            last_flush = time.monotonic()

        for idx in range(iterations):
            await emitter.emit(
                "iteration_start",
                "running",
                detail={"index": idx + 1},
                progress=0.2 + (0.6 * (idx / max(iterations, 1))),
            )
            def _stream_callback(event: dict[str, str]) -> None:
                token = event.get("token")
                if not token:
                    return
                token_buffer.append(token)
                if len("".join(token_buffer)) >= min_chars or (time.monotonic() - last_flush) * 1000 >= flush_ms:
                    emitter.emit_token_sync(
                        token="".join(token_buffer),
                        role=event.get("role", "pm"),
                        stage=event.get("stage", "pm"),
                        iteration=idx + 1,
                    )
                    token_buffer.clear()
                    last_flush = time.monotonic()

            if prompt_enhance_enabled:
                prompt_enhancement = enhancer.enhance(
                    message=current_message,
                    scope=scope.model_dump(),
                    context=context,
                    tool_results=[tool.model_dump() for tool in tool_results_out],
                    research=research,
                    citations_required=citations_required,
                    current_date=payload.current_date,
                    cutoff_date=payload.cutoff_date,
                )
                engine_message = prompt_enhancement.enhanced_message
            else:
                engine_message = f"{current_message}\n\n[HarnessContext]\n{context}"

            run, _state, response_text = await engine.run(
                message=engine_message,
                session_id=session_id,
                raise_on_error=False,
                stream_callback=_stream_callback,
                model_overrides=model_routing.overrides if model_routing else None,
            )
            flush_tokens(idx + 1)
            emitter.set_run(str(run.id), str(run.session_id))
            iteration_outputs.append(
                IterationOut(
                    index=idx + 1,
                    run_id=run.id,
                    status=run.status,
                    response=response_text,
                )
            )
            await emitter.emit(
                "iteration_done",
                run.status.value,
                detail={"index": idx + 1, "status": run.status.value},
                progress=0.2 + (0.6 * ((idx + 1) / max(iterations, 1))),
            )
            session_id = run.session_id
            if run.status != RunStatus.COMPLETED:
                break
            if budget_ms:
                elapsed_ms = (time.perf_counter() - iterations_start) * 1000
                if elapsed_ms >= budget_ms:
                    await emitter.emit(
                        "iteration_stop",
                        "budget",
                        detail={"elapsed_ms": elapsed_ms, "budget_ms": budget_ms},
                        progress=0.8,
                    )
                    break
            if prev_response:
                import difflib

                similarity = difflib.SequenceMatcher(None, prev_response, response_text).ratio()
                if similarity >= similarity_stop:
                    await emitter.emit(
                        "iteration_stop",
                        "converged",
                        detail={"similarity": similarity},
                        progress=0.8,
                    )
                    break
            prev_response = response_text
            if idx < iterations - 1:
                current_message = (
                    f"{payload.message}\n\n"
                    f"[Previous Response]\n{response_text}\n\n"
                    "Refine, correct, and improve the response."
                )
        timings["iterations_ms"] = (time.perf_counter() - iterations_start) * 1000

        ab_test_enabled = (
            payload.ab_test
            if payload.ab_test is not None
            else os.getenv("LANGLY_AB_TEST_DEFAULT", "false").lower() == "true"
        )
        if ab_test_enabled:
            await emitter.emit("ab_test", "start", progress=0.85)
            ab_test = await ABTester().run(
                message=payload.message,
                scope=scope.model_dump(),
                tool_results=[tool.model_dump() for tool in tool_results_out],
                response=response_text,
            )
            if ab_test.winner == "b":
                response_text = ab_test.variant_b
            await emitter.emit(
                "ab_test",
                "done",
                detail={"winner": ab_test.winner, "fallback": ab_test.fallback},
                progress=0.9,
            )
        await emitter.emit("postprocess", "start", progress=0.91)
        postprocess = ResponsePostProcessor().apply(
            response_text,
            research,
            enforce_citations=citations_required,
        )
        response_text = postprocess.response
        await emitter.emit(
            "postprocess",
            "done",
            detail={"citations_added": postprocess.citations_added},
            progress=0.915,
        )
        grade_enabled = (
            payload.grade
            if payload.grade is not None
            else os.getenv("LANGLY_GRADE_DEFAULT", "false").lower() == "true"
        )
        trace_builder = TraceBuilder()
        trace_task = asyncio.create_task(
            trace_builder.build(
                payload.message,
                scope.model_dump(),
                [tool.model_dump() for tool in tool_results_out],
                response_text,
            )
        )
        grade_task: asyncio.Task | None = None
        grade_start = None
        if grade_enabled:
            await emitter.emit("grade", "start", progress=0.92)
            grade_start = time.perf_counter()
            grade_task = asyncio.create_task(
                ResponseGrader().grade(
                    message=payload.message,
                    scope=scope.model_dump(),
                    tool_results=[tool.model_dump() for tool in tool_results_out],
                    response=response_text,
                )
            )

        trace_start = time.perf_counter()
        trace = await trace_task
        timings["trace_ms"] = (time.perf_counter() - trace_start) * 1000
        if grade_task is not None:
            grade = await grade_task
            if grade_start is not None:
                timings["grade_ms"] = (time.perf_counter() - grade_start) * 1000
            await emitter.emit(
                "grade",
                "done",
                detail={"summary": grade.summary, "fallback": grade.fallback},
                progress=0.95,
            )
        tuning_enabled = (
            payload.tuning
            if payload.tuning is not None
            else os.getenv("LANGLY_TUNING_DEFAULT", "false").lower() == "true"
        )
        if tuning_enabled:
            await emitter.emit("tuning", "start", progress=0.96)
            tuning = HarnessTuner().suggest(
                grade=grade.model_dump() if grade else None,
                tool_results=[tool.model_dump() for tool in tool_results_out],
                scope=scope.model_dump(),
            )
            await emitter.emit(
                "tuning",
                "done",
                detail={"actions": len(tuning.actions), "notes": tuning.notes},
                progress=0.97,
            )

        await emitter.emit(
            "kata_after",
            "done",
            detail={"steps": kata_plan.phases[2].steps if kata_plan else []},
            progress=0.98,
        )

        templates_enabled = (
            payload.task_templates
            if payload.task_templates is not None
            else os.getenv("LANGLY_TASK_TEMPLATES_DEFAULT", "false").lower() == "true"
        )
        if templates_enabled:
            task_templates_result = TaskTemplateEngine().suggest(payload.message, scope.model_dump())
            await emitter.emit(
                "task_templates",
                "done",
                detail={"templates": len(task_templates_result.templates), "reason": task_templates_result.reason},
                progress=0.975,
            )

        capture_enabled = (
            payload.task_capture
            if payload.task_capture is not None
            else os.getenv("LANGLY_TASK_CAPTURE_DEFAULT", "false").lower() == "true"
        )
        if capture_enabled:
            capture = TaskCapture()
            candidates = capture.extract(response_text)
            commit = (
                payload.task_capture_commit
                if payload.task_capture_commit is not None
                else os.getenv("LANGLY_TASK_CAPTURE_COMMIT", "false").lower() == "true"
            )
            if commit:
                task_capture_result = capture.commit(candidates)
            else:
                task_capture_result = TaskCaptureResult(
                    candidates=candidates,
                    created=[],
                    skipped=[c.description for c in candidates],
                    error=None,
                )
            await emitter.emit(
                "task_capture",
                "done",
                detail={"candidates": len(task_capture_result.candidates), "created": len(task_capture_result.created)},
                progress=0.98,
            )
    except Exception as exc:
        settings = get_settings()
        error_context = {
            "request_id": request_id,
            "session_id": str(payload.session_id) if payload.session_id else None,
            "mode": payload.mode,
            "auto_tools": runner.auto_tools,
            "scope": scope.model_dump(),
            "tools_used": [tool.model_dump() for tool in tool_results_out],
            "tool_selection": tool_selection.model_dump() if tool_selection else None,
            "research": research.model_dump() if research else None,
            "prompt_enhancement": prompt_enhancement.model_dump() if prompt_enhancement else None,
            "context_payload": context,
            "task_capture": task_capture_result.model_dump() if task_capture_result else None,
            "task_templates": task_templates_result.model_dump() if task_templates_result else None,
        }
        logger.exception(
            "harness run failed context=%s",
            json.dumps(jsonable_encoder(error_context)),
        )
        error_detail = {
            "error_type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc() if settings.debug else None,
            "context": error_context,
        }
        await emitter.emit(
            "error",
            "failed",
            detail=jsonable_encoder(error_detail),
            progress=1.0,
        )
        raise HTTPException(
            status_code=500,
            detail=jsonable_encoder(error_detail),
        ) from exc

    mermaid_keywords: list[str] = []
    for tool in tool_results_out:
        if tool.name == "mermaid" and isinstance(tool.output, dict):
            keywords = tool.output.get("keywords")
            if isinstance(keywords, list):
                mermaid_keywords = [str(k) for k in keywords if k]
            break

    mermaid = build_mermaid_graph(
        payload.message,
        scope.model_dump(),
        [tool.model_dump() for tool in tool_results_out],
        response_text,
        iterations=len(iteration_outputs),
        recovery=recovery is not None,
        research=research is not None and (research.used or bool(research.sources)),
        tuning=tuning is not None and bool(tuning.actions),
        keywords=mermaid_keywords or None,
    )
    timings["scope_ms"] = scope_ms
    timings["total_ms"] = (time.perf_counter() - start_total) * 1000
    await emitter.emit("complete", "done", detail={"status": run.status.value}, progress=1.0)

    run.result = jsonable_encoder(
        {
            "request_id": request_id,
            "response": response_text,
            "scope": scope.model_dump(),
            "tools": [tool.model_dump() for tool in tool_results_out],
            "tool_selection": tool_selection.model_dump() if tool_selection else None,
            "taskwarrior": taskwarrior.model_dump() if taskwarrior else None,
            "tool_reconfig": tool_reconfig.model_dump() if tool_reconfig else None,
            "research": research.model_dump() if research else None,
            "prompt_enhancement": prompt_enhancement.model_dump() if prompt_enhancement else None,
            "postprocess": postprocess.model_dump() if postprocess else None,
            "task_capture": task_capture_result.model_dump() if task_capture_result else None,
            "task_templates": task_templates_result.model_dump() if task_templates_result else None,
            "katas": kata_plan.model_dump() if kata_plan else None,
            "iterations": [item.model_dump() for item in iteration_outputs],
            "iterations_used": iterations_used,
            "iterations_auto": iterations_auto,
            "ab_test": ab_test.model_dump() if ab_test else None,
            "grade": grade.model_dump() if grade else None,
            "model_routing": model_routing.model_dump() if model_routing else None,
            "recovery": recovery.model_dump() if recovery else None,
            "tuning": tuning.model_dump() if tuning else None,
            "trace": trace.model_dump(),
            "mermaid": mermaid,
            "timings": timings,
            "cached": False,
        }
    )
    RunStore().update_run(run.id, run.status, run.result, run.error)

    delta = StateDelta(
        run_id=run.id,
        node="harness_trace",
        changes={
            "request_id": request_id,
            "scope": scope.model_dump(),
            "tools": [tool.model_dump() for tool in tool_results_out],
            "tool_selection": tool_selection.model_dump() if tool_selection else None,
            "taskwarrior": taskwarrior.model_dump() if taskwarrior else None,
            "tool_reconfig": tool_reconfig.model_dump() if tool_reconfig else None,
            "research": research.model_dump() if research else None,
            "prompt_enhancement": prompt_enhancement.model_dump() if prompt_enhancement else None,
            "postprocess": postprocess.model_dump() if postprocess else None,
            "task_capture": task_capture_result.model_dump() if task_capture_result else None,
            "task_templates": task_templates_result.model_dump() if task_templates_result else None,
            "katas": kata_plan.model_dump() if kata_plan else None,
            "iterations": [item.model_dump() for item in iteration_outputs],
            "iterations_used": iterations_used,
            "iterations_auto": iterations_auto,
            "ab_test": ab_test.model_dump() if ab_test else None,
            "grade": grade.model_dump() if grade else None,
            "model_routing": model_routing.model_dump() if model_routing else None,
            "recovery": recovery.model_dump() if recovery else None,
            "tuning": tuning.model_dump() if tuning else None,
            "trace": trace.model_dump(),
            "mermaid": mermaid,
            "timings": timings,
            "cached": False,
        },
    )
    delta_payload = jsonable_encoder(delta.model_dump())
    RunStore().save_delta(delta_payload)
    await get_event_bus().publish({"type": "state_delta", "delta": delta_payload})

    response_payload = HarnessRunResponse(
        run_id=run.id,
        session_id=run.session_id,
        request_id=request_id,
        status=run.status,
        response=response_text,
        scope=scope,
        available_tools=available_tools,
        tools_used=tool_results_out,
        tool_selection=ToolSelectionOut(**tool_selection.model_dump()) if tool_selection else None,
        taskwarrior=taskwarrior,
        tool_reconfig=tool_reconfig,
        research=ResearchOut(**research.model_dump()) if research else None,
        prompt_enhancement=PromptEnhancementOut(
            applied=prompt_enhancement.applied,
            notes=prompt_enhancement.notes,
            citations_required=prompt_enhancement.citations_required,
            current_date=prompt_enhancement.current_date,
            cutoff_date=prompt_enhancement.cutoff_date,
            sources=[ResearchSourceOut(**src.model_dump()) for src in prompt_enhancement.sources],
        )
        if prompt_enhancement
        else None,
        postprocess=PostprocessOut(
            citations_added=postprocess.citations_added,
            warnings=postprocess.warnings,
        )
        if postprocess
        else None,
        task_capture=TaskCaptureOut(
            candidates=[
                TaskCandidateOut(
                    description=candidate.description,
                    source=candidate.source,
                    tags=candidate.tags,
                )
                for candidate in task_capture_result.candidates
            ],
            created=task_capture_result.created,
            skipped=task_capture_result.skipped,
            error=task_capture_result.error,
        )
        if task_capture_result
        else None,
        task_templates=TaskTemplateResultOut(
            templates=[
                TaskTemplateOut(name=template.name, checklist=template.checklist)
                for template in task_templates_result.templates
            ],
            reason=task_templates_result.reason,
        )
        if task_templates_result
        else None,
        katas=KataPlanOut(
            intent=kata_plan.intent,
            phases=[
                KataPhaseOut(name=phase.name, steps=phase.steps)
                for phase in kata_plan.phases
            ],
        )
        if kata_plan
        else None,
        iterations=iteration_outputs,
        iterations_used=iterations_used,
        iterations_auto=iterations_auto,
        ab_test=ab_test,
        grade=grade,
        model_routing=model_routing,
        recovery=recovery,
        tuning=TuningOut(
            actions=[TuningActionOut(kind=action.kind, detail=action.detail) for action in tuning.actions],
            notes=tuning.notes,
        )
        if tuning
        else None,
        trace=TraceOut(**trace.model_dump()),
        mermaid=mermaid,
        timings=timings,
        cached=False,
    )
    cache.set(cache_key, response_payload.model_dump())
    return response_payload


@router.post("/batch", response_model=HarnessBatchResponse)
async def run_harness_batch(payload: HarnessBatchRequest) -> HarnessBatchResponse:
    batch_id = payload.request_id or str(uuid4())
    tuner = HarnessTuner()
    state = TuningState()
    runs: list[HarnessRunResponse] = []
    tuning_actions: list[list[TuningActionOut]] = []

    for idx, message in enumerate(payload.messages, start=1):
        if not message:
            continue
        req = HarnessRunRequest(
            message=message,
            mode=payload.mode,
            auto_tools=state.auto_tools or payload.auto_tools,
            iterations=state.iterations or payload.iterations,
            request_id=f"{batch_id}-{idx}",
            ab_test=payload.ab_test,
            grade=payload.grade if payload.grade is not None else True,
            research=state.research if state.research is not None else payload.research,
            research_query=payload.research_query,
            prompt_enhance=state.prompt_enhance if state.prompt_enhance is not None else payload.prompt_enhance,
            citations=state.citations if state.citations is not None else payload.citations,
            tool_selection=payload.tool_selection,
            tuning=payload.tuning,
            task_capture=payload.task_capture,
            task_capture_commit=payload.task_capture_commit,
            task_templates=payload.task_templates,
            force=True,
        )
        run = await run_harness(req)
        runs.append(run)

        if payload.tuning:
            summary = tuner.suggest(
                grade=run.grade.model_dump() if run.grade else None,
                tool_results=[tool.model_dump() for tool in run.tools_used],
                scope=run.scope.model_dump(),
            )
            actions = [
                TuningActionOut(kind=action.kind, detail=action.detail)
                for action in summary.actions
            ]
            tuning_actions.append(actions)
            state = tuner.apply(state, summary)
        else:
            tuning_actions.append([])

    final_state = None
    if payload.tuning:
        final_state = TuningStateOut(**state.model_dump())
    return HarnessBatchResponse(
        batch_id=batch_id,
        runs=runs,
        tuning_actions=tuning_actions,
        final_state=final_state,
    )
