# Langly V2 Architecture (Scaffold)

## Goals
- Keep the hierarchical PM -> specialists concept.
- Add transactional state updates with clear error handling.
- Introduce a bounded memory model with pruning and summarization hooks.
- Prepare for tool registry and safety gating.
- Keep Ollama + Granite models as the execution backend.

## Core Components

### Runtime State
- Canonical Pydantic models in app/runtime/models.py.
- StateDelta as the unit of change for transactional updates.
- InMemoryStateStore commits deltas and maintains checkpoints.
- WorkflowRun metadata to track execution lifecycle.

### Workflow Engine
- app/runtime/engine.py runs PM, routing, specialist steps, and synthesis.
- Uses a bounded memory store for the conversation window.
- Uses a circuit breaker to prevent repeated failures.

### Router
- app/runtime/router.py uses keyword routing first.
- Falls back to Granite MoE for semantic routing.

### LLM Provider
- app/runtime/llm.py wraps ChatOllama.
- Per-role model mapping via app/core/constants.py.
- Fallback chain for degraded model availability.

### Reliability
- app/runtime/circuit_breaker.py implements a simple consecutive failure breaker.
- app/runtime/errors.py provides structured error kinds.

### Memory
- app/runtime/memory.py provides bounded memory with pruning.
- Summarization is a placeholder that records a summary note.
- app/runtime/summarizer.py can condense older messages using the PM model.
 - app/runtime/neo4j_adapter.py provides optional summary persistence.

## Transactional Execution (Planned)
- Each node returns a StateDelta.
- StateDelta is validated and committed to the state store.
- Failures roll back to the last checkpoint.

## Tool Registry (Planned)
- Tools become first-class nodes with schema validation.
- Tool calls are stored in the state and audited.
- Guardian checks gate high-risk tools.

Current:
- Tool registry and Guardian gate are scaffolded in app/runtime/tools.
- HITL scaffolding is available in app/runtime/hitl.py.
- Engine can parse ```tools``` blocks and execute registered tools.
- HITL API endpoints are available at /api/v2/hitl/*.
- WebSocket delta stream is available at /api/v2/ws/deltas.
- Approved HITL requests can resume pending tool execution.
- Run deltas are persisted to SQLite and can be fetched via /api/v2/runs/{run_id}/deltas.
- Run listing is available at /api/v2/runs.
- Run detail is available at /api/v2/runs/{run_id}.
- HITL pending requests list is available at /api/v2/hitl/requests.
- Dashboard aggregation is available at /api/v2/dashboard.
- Tool approvals emit state deltas and are persisted to the run store.
- State snapshots are stored and available at /api/v2/snapshots/{session_id}.
- Latest snapshot available at /api/v2/snapshots/{session_id}/latest.
- Recent deltas available at /api/v2/recent/deltas.
- V2 health available at /api/v2/health/v2.
- Seed run endpoint available at /api/v2/seed/run.
- Status endpoint available at /api/v2/status.
- Config endpoint available at /api/v2/config.
- Overview endpoint available at /api/v2/overview.
- Metrics endpoint available at /api/v2/metrics.
- Reset endpoint available at /api/v2/reset.
- Cleanup endpoint available at /api/v2/cleanup/prune.
- Diagnostics endpoint available at /api/v2/diagnostics.
- Summary endpoint available at /api/v2/summary.
- Models endpoint available at /api/v2/models.
- Neo4j endpoint available at /api/v2/neo4j.
- Docs index endpoint available at /api/v2/docs.

Tool Call Format:
```tools
{
  "tool_calls": [
    { "name": "echo", "arguments": { "text": "hello" } }
  ]
}
```

Approval Tool:
```tools
{
  "tool_calls": [
    { "name": "approval_required", "arguments": { "action": "deploy" } }
  ]
}
```

## Future Work
- Add parallel graph branches for independent tasks.
- Implement persistent state storage and time travel.
- Add optional Neo4j memory and embeddings.
