# Changelog (Repo Overview)

This file summarizes the current repo state and the major components that are implemented.

## Highlights
- Dual runtime architecture: **V2** (LangGraph-based, production runtime) + **V3** (experimental graph-first runtime).
- Versioned API surface with explicit v2/v3 endpoints and WebSocket delta streams.
- Reliability layer includes circuit breaker, loop detection, health checks, and graceful degradation.
- Tooling + HITL flows are implemented for both runtimes with separate registries.

## Release Summary (Current Snapshot)
- README and docs align to the current API surface and runtime split.
- V2 full endpoint list is documented; V3 endpoints and WS deltas are documented.
- Architecture diagrams reflect the v2/v3 runtime split and delta streams.
- I/O examples are documented in `docs/IO_EXAMPLES.md`.
- Single chat harness UI at `/static/index.html` backed by `/api/v2/harness/run`.

## V2 Runtime
- LangGraph workflows with PM + specialist agents.
- SQLite-backed run storage and event deltas.
- HITL approvals, sessions, runs, timeline, snapshots, summary, and diagnostics endpoints.
- Neo4j memory integration (v2 only).

## V3 Runtime
- Graph-first engine with event-sourced deltas and async SQLite storage.
- Small-model registry + fallbacks (<=3B models).
- Typed tools, approval-required tools, and HITL resume flow.
- WebSocket delta streaming at `/api/v3/ws/deltas`.

## API Surface
- **V1 (legacy)**: `/api/v1/health`, `/api/v1/workflows`, `/api/v1/agents`, `/api/v1/chat`, `WS /ws`.
- **V2 (primary)**: `/api/v2/*`, `WS /api/v2/ws/deltas`.
- **V3 (experimental)**: `/api/v3/*`, `WS /api/v3/ws/deltas`.
- Full endpoint lists: `docs/V2_ENDPOINTS.md`, `docs/V3_ENDPOINTS.md`.

## Reliability / Health
- Circuit breaker, loop detection, health checks, and graceful degradation utilities.
- Health endpoints for v1 and v2, plus runtime diagnostics endpoints.

## Tests / Tooling
- Test suites organized under `tests/unit`, `tests/e2e`, `tests/v2`, and `tests/v3`.
- Scripts/Makefile provide lint/test helpers.

## Docs
- Architecture and runtime docs in `docs/ARCHITECTURE_V2.md`, `docs/ARCHITECTURE_V3.md`, and `docs/OVERVIEW.md`.
- Endpoint documentation in `docs/V2_ENDPOINTS.md` and `docs/V3_ENDPOINTS.md`.
