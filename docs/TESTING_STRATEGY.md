# Testing Strategy

## Scope

This plan covers the harness runtime (v2), research/citations pipeline, MCP browser tooling, and UI updates.
It favors fast unit tests plus lightweight integration checks over long-running E2E runs.

## Unit Tests

Focus on deterministic policies and post-processing:

- Research policy + URL extraction
- Tool selection policy
- Response post-processing (citations)
- Tuning heuristics

Run:

```bash
pytest -q tests/unit/test_harness_policies.py
```

## Integration Tests

### Harness run (local)

```bash
curl -s http://localhost:8000/api/v2/harness/run \
  -H "Content-Type: application/json" \
  -d '{"message":"Explain what Langly does","grade":true}'
```

### Harness batch tuning

```bash
curl -s http://localhost:8000/api/v2/harness/batch \
  -H "Content-Type: application/json" \
  -d '{"messages":["Summarize README"],"grade":true,"tuning":true}'
```

### Searx mock (optional)

If Searx is not available, run a local stub and point `LANGLY_SEARX_URL` to it.

## UI Smoke Tests

- Load `http://localhost:8000/static/index.html`
- Send a prompt and confirm streaming tokens, status timeline, and tool cards update
- Toggle research/citations and verify Research panel populates

## Load / Soak (optional)

Run 10 sequential harness requests and review timings:

```bash
for i in $(seq 1 10); do
  curl -s http://localhost:8000/api/v2/harness/run \
    -H "Content-Type: application/json" \
    -d '{"message":"Quick status check","grade":false}' >/dev/null
  sleep 0.5
done
```

## CI Suggestions

- Run unit tests only (fast)
- Skip network-dependent tests by default
- Add a nightly job to run full harness integration if Ollama is available

Example:

```bash
pytest -q tests/unit
```
