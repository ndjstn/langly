# Langly V3 Rewrite Plan (TinyLLM Graph Runtime)

This plan builds a from-scratch, graph-first runtime that uses small specialized models (<=3B). V2 remains stable while V3 is built in parallel.

## Milestone M0 - Alignment and Scope
- Decisions: single V3 source of truth, small-model constraint, event-sourced state.
- Freeze v2 feature growth; only critical fixes.
- Draft V3 architecture and contracts.

Acceptance
- ARCHITECTURE_V3.md published.
- Data contracts agreed (Run, StateDelta, Task, ToolCall, Approval).

Dependencies
- None.

Risks
- Scope creep.
Mitigation
- Keep V3 targets minimal; defer non-core features.

## Milestone M1 - Event-Sourced Data Layer
- Implement async DB store for runs and deltas.
- Add snapshot derivation and replay utilities.
- Add deterministic ID strategy and indexes.

Acceptance
- Deltas persist and replay builds state for a run.
- Snapshots can be generated without data loss.

Dependencies
- M0.

Risks
- DB contention and latency.
Mitigation
- Async DB layer; batch writes; indexes.

## Milestone M2 - Graph Engine Core
- Node interface (stateless) with typed inputs/outputs.
- Graph executor with parallel branches and bounded concurrency.
- Per-node circuit breaker and retry policy.

Acceptance
- Router + Planner + Specialist + Synthesizer executes end-to-end.
- Parallel branches complete and join deterministically.

Dependencies
- M1.

Risks
- Non-determinism in parallel branches.
Mitigation
- Deterministic join ordering and stable IDs.

## Milestone M3 - Model Registry (Small-Model Only)
- Model registry with role-based mapping and fallback chains.
- Capabilities metadata (latency, max tokens).
- Config-driven overrides.

Acceptance
- Roles resolve to small models only.
- Fallback chain is exercised on failure.

Dependencies
- M2.

Risks
- Small models underperform for complex tasks.
Mitigation
- Multi-hop prompts; specialized node chaining.

## Milestone M4 - Tools + HITL
- Typed tool registry with schema validation.
- Safety gate (Guardian + rules) before execution.
- Approval flow that pauses and resumes runs.

Acceptance
- Tool calls produce deltas and are auditable.
- Approval-required tools block and resume cleanly.

Dependencies
- M2.

Risks
- Tool misuse or unsafe side effects.
Mitigation
- Mandatory approvals for destructive tools; audit log.

## Milestone M5 - Memory + Retrieval
- Bounded episodic memory with pruning.
- Optional semantic retrieval and embeddings.
- Optional Neo4j adapter for graph memory.

Acceptance
- Memory stays bounded with consistent behavior.
- Retrieval can enrich prompts with prior decisions.

Dependencies
- M2.

Risks
- Memory bloat and slow queries.
Mitigation
- Aggressive pruning; caching.

## Milestone M6 - API + UI Integration
- /api/v3 endpoints for runs, deltas, tools, HITL.
- WebSocket delta stream.
- UI wiring for V3 selection and visual graph view.

Acceptance
- UI can run a V3 workflow and display deltas.

Dependencies
- M2, M4.

Risks
- UI complexity.
Mitigation
- Progressive enhancement and minimal viable views.

## Milestone M7 - Testing + Production Hardening
- Unit tests for core engine, store, tool gating.
- Integration tests for API workflows.
- Metrics, traces, and health checks.

Acceptance
- CI passes with >=80 percent coverage on V3 core.
- Load test with concurrent runs.

Dependencies
- M6.

Risks
- Hidden regressions during migration.
Mitigation
- Parallel v2/v3 runs and diffing.
