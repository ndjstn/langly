# Langly V2 Rewrite Plan

## Phase 1: Foundation (current scaffold)
- Add v2 runtime package (models, errors, memory, circuit breaker).
- Implement GraniteLLMProvider with role-based model selection.
- Add WorkflowEngine with single PM step.
- Add /api/v2/workflows/run endpoint.

Acceptance:
- FastAPI serves /api/v2/workflows/run.
- PM step returns a response from Ollama.
- Bounded memory prunes after max_messages.
- Circuit breaker blocks after consecutive failures.

## Phase 2: Graph + Router
- Define WorkflowState + StateDelta for graph nodes.
- Add Router agent (Granite MoE) and routing rules.
- Add PM -> Specialist delegation path.
- Add aggregation/synthesis step.

Acceptance:
- Router selects agent based on task type.
- PM delegates to specialist and receives result.
- StateDelta commits succeed or roll back on failure.

Status:
- Router + delegation implemented in v2 engine.

## Phase 3: Tools + HITL
- Add tool registry with schemas and approvals.
- Add Guardian safety checks before tool execution.
- Add HITL approval workflow and time travel checkpoints.

Acceptance:
- Tool calls are logged and gated.
- HITL can approve/reject tool execution.
- Checkpoint rollback restores state.

Status:
- Tool registry + guardian gate scaffolded in v2 runtime.
- HITL approval manager scaffolded in v2 runtime.
- Tool call parsing + execution wired in v2 engine.
- HITL API endpoints added under /api/v2/hitl.
- State delta WebSocket stream added under /api/v2/ws/deltas.
- Memory summarizer added and wired to the v2 engine.
- Optional Neo4j adapter added for summary persistence.
- HITL approval now resumes pending tool execution.
- SQLite run store added with /api/v2/runs/{run_id}/deltas.
- Run listing endpoint added at /api/v2/runs.
- Run detail endpoint added at /api/v2/runs/{run_id}.
- HITL request listing and pending tool listing endpoints added.
- Run summaries now include tool/task counts.
- Dashboard aggregation endpoint added at /api/v2/dashboard.
- Tool approvals now append deltas to run history.
- State snapshots now persist in SQLite and can be listed per session.
- Latest snapshot endpoint added at /api/v2/snapshots/{session_id}/latest.
- Recent deltas endpoint added at /api/v2/recent/deltas.
- Basic v2 endpoint smoke test added.
- V2 health endpoint added at /api/v2/health/v2.
- Run store test added.
- V2 endpoint docs added in docs/V2_ENDPOINTS.md.
- Approval-required tool added for HITL flow.
- V2 quickstart added to README.
- Tool registry approval test added.
- Seed run endpoint added for UI testing.
- Status endpoint added at /api/v2/status.
- v2 ping script added at scripts/v2_ping.sh.
- Config endpoint added at /api/v2/config.
- Seed + fetch script added at scripts/v2_seed_and_fetch.sh.
- V2 status and timeline tests added.
- Overview endpoint added at /api/v2/overview.
- Integration test added for seed -> runs flow.
- Metrics endpoint added at /api/v2/metrics.
- Snapshot listing test added.
- Prune script added at scripts/v2_prune.sh.
- Reset endpoint added at /api/v2/reset.
- Overview + metrics tests added.
- Latest run script added at scripts/v2_latest.sh.
- Cleanup endpoint added at /api/v2/cleanup/prune.
- Config/reset tests added.
- Cleanup test added.
- Diagnostics endpoint added at /api/v2/diagnostics.
- Run+approve script added at scripts/v2_run_and_approve.py.
- Diagnostics test added.
- Summary endpoint added at /api/v2/summary.
- Summary + config tests added.
- Models endpoint added at /api/v2/models.
- Neo4j diagnostic endpoint added at /api/v2/neo4j.
- Models + Neo4j tests added.
- Docs index endpoint added at /api/v2/docs.
- Startup check script added at scripts/v2_startup_check.sh.

## Phase 4: Memory + Neo4j (optional)
- Add summarization worker and auto-pruning strategy.
- Add Neo4j memory stores with embeddings.
- Implement retrieval-augmented prompts.

Acceptance:
- Memory stays bounded with stable responses.
- Neo4j retrieval works for past tasks and summaries.
