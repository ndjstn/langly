# Langly V3 Architecture (TinyLLM Graph Runtime)

> **Current vs Planned:** This document describes the V3 architecture vision. Components marked\n+> as “planned” are not yet implemented. Refer to the V3 code under `app/v3` for the current\n+> runtime capabilities.\n+
## Context
V3 is a from-scratch runtime that prioritizes a graph-first execution model and small specialized models (<=3B) while keeping FastAPI, Ollama, and Neo4j optional. The goal is a deterministic, observable, and fault-tolerant multi-agent platform that runs on local hardware.

## Goals
- Graph-native execution with explicit nodes, edges, and concurrency.
- Small-model first approach with role-based specialization and fallback chains.
- Event-sourced state updates with immutable deltas and replayability.
- Stateless agent primitives that are easy to test and scale.
- Production-grade reliability, observability, and HITL safety gates.

## Non-goals
- Full parity with v1 LangGraph workflows.
- Tight coupling to any single database (Neo4j stays optional).
- Hidden side effects or opaque agent logic.

## Principles
- Small-model first (<=3B) with fallback chains.
- Graph-native state: nodes and edges are first-class data.
- Stateless agents: inputs + state => outputs + deltas.
- Event-sourced execution: deltas are the system of record.
- Observable-by-default: every decision emits a delta and trace.

## Core Components

### Graph Engine
- Planned: DAG of nodes (router, planner, specialists, verifier, synthesizer).
- Planned: parallel branches with bounded concurrency.
- Emits deltas for node entry/exit and tool calls.
- Planned: circuit breakers and retry policies per node.
- Current implementation includes router + planner nodes and tool-call parsing with sequential execution.

### State Store (Event Sourced)
- Immutable StateDelta records are the source of truth.
- Snapshots are derived for fast reads and time-travel.
- Supports replay to rebuild state for audits and debugging.
- Implemented with async SQLite in `app/v3/store.py`.

### Model Registry
- Role-to-model mapping with explicit small-model constraints.
- Fallback chains per role and per node.
- Centralized model capability metadata (latency, context size).

### Tool System
- Typed tools with Pydantic input/output schemas.
- Tool calls are logged as deltas with structured metadata.
- Implemented registry + built-ins (`echo`, `approval_required`) under `app/v3/tools`.
- Planned: safety gates (Guardian + rules) before execution.

### HITL (Human-in-the-Loop)
- Approval requests are first-class records.
- Run execution can pause/resume based on approvals.
- Rejections create explicit failure deltas.
- V3 HITL endpoints support approval resolution and resume flow.

### Memory + Retrieval
- Bounded episodic memory with deterministic pruning.
- Optional semantic retrieval using embeddings.
- Optional Neo4j graph memory adapter.

### Observability
- WebSocket delta stream for UI updates.
- V3 delta stream is available at `/api/v3/ws/deltas`.
- Planned: metrics for node latency, retries, and tool usage.
- Planned: traces for end-to-end workflow visibility.

## Data Contracts (Pydantic-style)

### Run
- id: UUID
- session_id: UUID
- status: CREATED | RUNNING | COMPLETED | FAILED | PAUSED
- created_at: datetime
- updated_at: datetime
- result: dict | None
- error: str | None
- metadata: dict

### StateDelta
- id: UUID
- run_id: UUID
- node_id: str
- kind: USER_INPUT | NODE_START | NODE_END | TOOL_CALL | APPROVAL | ERROR
- changes: dict
- errors: list[ErrorRecord]
- created_at: datetime

### Task
- id: UUID
- description: str
- assigned_agent: str | None
- status: PENDING | IN_PROGRESS | COMPLETED | FAILED
- result: str | None
- metadata: dict

### ToolCall
- id: UUID
- name: str
- arguments: dict
- status: PENDING | COMPLETED | FAILED | APPROVAL_REQUIRED
- result: object | None
- error: str | None
- metadata: dict

### Approval
- id: UUID
- run_id: UUID
- prompt: str
- status: PENDING | APPROVED | REJECTED
- context: dict
- created_at: datetime
- resolved_at: datetime | None

## Execution Graph (Baseline)
- Input -> Router -> Planner -> Specialist fan-out -> Verifier -> Synthesizer
- Specialists execute in parallel with a concurrency cap.
- Tool calls can interrupt flow and await approval.

## Storage Strategy
- Async DB access (SQLite for dev; Postgres recommended for prod).
- Current tables: runs, deltas.
- Planned tables: tasks, tool_calls, approvals, snapshots.
- Snapshots are derived from deltas and are not authoritative.

## Model Registry (Initial Map)
- router: granite3-moe:1b
- planner: granite3.1-dense:2b
- coder: granite-code:3b
- reviewer: granite-code:3b
- tester: granite-code:3b
- docs: granite3.1-dense:2b
- summarizer: phi-3-mini:3b (or granite3.1-dense:2b fallback)
- embeddings: granite-embedding:278m

## API Surface (Initial)
- POST /api/v3/workflows/run
- GET /api/v3/runs
- GET /api/v3/runs/{run_id}
- GET /api/v3/runs/{run_id}/deltas
- GET /api/v3/tools
- POST /api/v3/tools/call
- GET /api/v3/hitl/requests
- POST /api/v3/hitl/requests/{request_id}/resolve
- WebSocket /api/v3/ws/deltas

## Migration Notes
- V2 remains operational during V3 development.
- No shared runtime DB between V2 and V3.
- A future migration tool can replay V2 runs into V3 deltas.

## Open Questions
- When to promote Neo4j to primary store vs optional adapter?
- Which small model variants are acceptable for code review quality?
- Do we want a centralized scheduler or a distributed task market?
