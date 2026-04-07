# Langly Overview

## What This Repo Contains
Langly is a multi-agent coding platform with two runtimes:

- **V2 (current default)**: LangGraph-based runtime with PM + specialists, HITL, tools, SQLite run history, Neo4j-backed memory, and a v2 API surface.
- **V3 (experimental)**: From-scratch, graph-first runtime with small specialized models (<=3B), event-sourced deltas, async SQLite storage, and minimal but extensible APIs.

## V2 vs V3 (Quick Comparison)

| Area | V2 | V3 |
| --- | --- | --- |
| Execution | LangGraph orchestration | Graph-first runtime (custom) |
| Models | Granite 8B / 3B mix | Small models only (<=3B) |
| State | In-memory + SQLite deltas | Event-sourced deltas + async SQLite |
| Tools | V2 registry + HITL | V3 registry + HITL (approval resume) |
| Observability | V2 delta WS stream | V3 delta WS stream |
| Status | Primary runtime | Experimental |

## API Surface (Summary)
- **Legacy (v1)**: `/api/v1/health`, `/api/v1/workflows`, `/api/v1/agents`, `/api/v1/chat`, `WS /ws`
- **V2 (primary UI/runtime)**: `/api/v2/*` including `/api/v2/harness/run`, `WS /api/v2/ws/deltas`
- **V3 (experimental)**: `/api/v3/*`, `WS /api/v3/ws/deltas`

## V3 UI Status

The web UI is still wired to V2 endpoints; V3 is currently API-first and headless.
Full UI integration is planned via WebSocket delta streams (`/api/v3/ws/deltas`),
enabling real-time observability of V3 runs, tool calls, and approvals.

The primary UI is a single chat harness served at `/static/index.html`.

## Core Components (V3)
- **Graph Engine**: Stateless nodes with explicit deltas.
- **Model Registry**: Role-based small model selection + fallbacks.
- **Event Store**: Async SQLite for runs and deltas.
- **Tools + HITL**: Typed tools with approval flow and tool-call deltas.
- **WebSocket Deltas**: Live updates over `/api/v3/ws/deltas`.

## V3 Quickstart

Note: The static UI is wired to V2 endpoints. V3 is API-first for now.

Run a workflow:

```bash
curl -s http://localhost:8000/api/v3/workflows/run \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello from v3"}'
```

List runs:

```bash
curl -s http://localhost:8000/api/v3/runs
```

List tools:

```bash
curl -s http://localhost:8000/api/v3/tools
```

Call a tool:

```bash
curl -s http://localhost:8000/api/v3/tools/call \
  -H "Content-Type: application/json" \
  -d '{"name":"echo","arguments":{"text":"hi"}}'
```

Approval-required tool:

```bash
curl -s http://localhost:8000/api/v3/tools/call \
  -H "Content-Type: application/json" \
  -d '{"name":"approval_required","arguments":{"action":"deploy"}}'
```

List approval requests:

```bash
curl -s http://localhost:8000/api/v3/hitl/requests
```

Resolve an approval:

```bash
curl -s http://localhost:8000/api/v3/hitl/requests/<request_id>/resolve \
  -H "Content-Type: application/json" \
  -d '{"approved": true}'
```

V3 database path:

```bash
export V3_DB_PATH=./runtime_v3.db
```

## Docs
- V2 architecture: `docs/ARCHITECTURE_V2.md`
- V2 endpoints: `docs/V2_ENDPOINTS.md`
- V3 endpoints: `docs/V3_ENDPOINTS.md`
- V3 architecture: `docs/ARCHITECTURE_V3.md`
- V3 rewrite plan: `docs/REWRITE_PLAN_V3.md`
- Repo overview: `docs/CHANGELOG.md`
- I/O examples: `docs/IO_EXAMPLES.md`
