# Langly Multi-Agent Coding Platform

A production-grade, parallel multi-agent coding platform using LangChain, LangGraph, Pydantic, FastAPI, and Ollama with IBM Granite models.

## Overview

Langly is a hierarchical agent system where you interact as a business owner with a Project Manager agent, who coordinates specialized worker agents including Coder, Code Reviewer, Architect, Tester, and Documentation agents. Each agent operates as an independent node in a LangGraph StateGraph with its own scratchpad, tools, and role-specific prompts.

The platform includes two runtimes: **V2** (LangGraph-based, production-ready) and **V3** (experimental graph-first runtime with event-sourced storage and small models).

## Features

- **Hierarchical Multi-Agent Architecture**: PM Agent coordinates Coder, Architect, Tester, Reviewer, and Documentation agents
- **Parallel Execution**: Independent tasks run concurrently using LangGraph's parallel branch nodes
- **IBM Granite Models**: Leverages Granite Dense, MoE, Code, Guardian, and Embedding models via Ollama
- **Graph-Based Memory (V2)**: Neo4j stores conversation history, project knowledge, and error patterns
- **Event-Sourced Storage (V3)**: Async SQLite with delta streaming for runs and tool calls
- **Human-in-the-Loop**: HITL approvals with resume flow, intervention points, and time-travel debugging
- **Tool Extensibility**: Typed tools with HITL approvals, dynamic registration, file system, code execution, git integration
- **Reliability Systems**: Circuit breaker, loop detection, health checks, and graceful degradation
- **Modern UI**: Chat-first streaming, collapsible panels, mermaid graphs, file navigator, copy buttons
- **WebSocket Deltas**: Real-time run updates via `/api/v3/ws/deltas` (V3)

## Quick Start

### Prerequisites

- Python 3.12+
- [Ollama](https://ollama.ai/) with IBM Granite models
- [Neo4j](https://neo4j.com/) database (required for v2 memory, optional for v3)
- [uv](https://docs.astral.sh/uv/) package manager (recommended)

### Installation

```bash
# Clone the repository
git clone https://github.com/ndjstn/langly.git
cd langly

# Install dependencies using uv
uv sync

# Or using pip
pip install -e .
```

### Configure Environment

Create a `.env` file in the project root (you can start from `.env.example`):

```bash
# Application
APP_NAME=langly
DEBUG=true
LOG_LEVEL=DEBUG

# Ollama
OLLAMA_BASE_URL=http://localhost:11434

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
NEO4J_DATABASE=langly

# API
API_HOST=0.0.0.0
API_PORT=8000

# Workflow
MAX_ITERATIONS=50
WORKFLOW_TIMEOUT=300
```

### Pull Granite Models

```bash
# Core models
ollama pull granite3.1-dense:8b
ollama pull granite3.1-dense:2b
ollama pull granite3-moe:3b
ollama pull granite3-moe:1b

# Code models
ollama pull granite-code:8b
ollama pull granite-code:3b

# Embedding model
ollama pull granite-embedding:278m

# Guardian model (safety)
ollama pull granite-guardian:8b
```

### Start Services

```bash
# Start Neo4j (using Docker)
docker run -d \
  --name langly-neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your_password \
  neo4j:5-community

# Start the FastAPI server
uvicorn app.api.app:app --reload --host 0.0.0.0 --port 8000
```

Optional Flask UI:

```bash
python -m flask --app flask_ui.app --debug run --host 0.0.0.0 --port 5001
```

### Access the Application

- **Chat Harness UI**: http://localhost:8000/static/index.html
- **Flask Harness UI (optional)**: http://localhost:5001
- **API Docs**: http://localhost:8000/docs
  
**Note**: The chat harness uses `/api/v2/harness/run` and streams deltas from `/api/v2/ws/deltas` or `/api/v3/ws/deltas`.

**Auto tools**: The harness runs `greptile`, `lint`, `jj`, and `taskwarrior` by default (with optional MCP browser). Tool selection can prune these automatically; you can override in the UI.

### Harness Enhancements (v2)

- **Streaming tokens** in the chat window via `/api/v2/ws/deltas`
- **Collapsible panels + file navigator** (`/api/v2/files/tree`, `/api/v2/files/read`, `/api/v2/files/upload`)
- **Tool selection + reconfiguration** based on scope and JJ recovery plan
- **Research + citations** with Searx (`LANGLY_SEARX_URL`) and optional citation enforcement
- **Prompt enhancement** (current date, model cutoff, tool summary, sources)
- **Batch tuning** for iterative improvements (`/api/v2/harness/batch`)
- **MCP browser** tool support (Chrome DevTools or Playwright MCP servers)
- **Task capture + templates** to surface checklists or sync to Taskwarrior (optional)
- **Preflight** tool to check file paths quickly (non-LLM)
- **Vision hooks** for MCP browser screenshots (optional command)

Example batch run:

```bash
curl -s http://localhost:8000/api/v2/harness/batch \\
  -H "Content-Type: application/json" \\
  -d '{
    "messages": ["Summarize the repo", "List failing tests"],
    "grade": true,
    "research": true,
    "citations": true,
    "tuning": true
  }'
```

Or run the helper script:

```bash
python scripts/harness_batch.py --host http://localhost:8000 --tuning --research --citations
```

MCP browser script example (auto navigate + snapshot):

```bash
export LANGLY_MCP_BROWSER_URL=http://localhost:3001/mcp
export LANGLY_MCP_BROWSER_AUTO=true
```

Vision pipeline example (runs after screenshots):

```bash
export LANGLY_VISION_PIPELINE_CMD="python scripts/vision_pipeline.py --image {{image}}"
```

Background monitoring helpers:

```bash
nohup scripts/ollama_watch.sh /tmp/ollama-watch.log 2 &
nohup scripts/harness_loop.sh 10 /tmp/harness-loop.log &
```

### Memory + Notes (Zettelkasten)

Langly can store and retrieve lightweight notes for katas, research summaries, and run retrospectives.

- Notes API: `/api/v2/notes`
- Design: `docs/memory-architecture.md`

Environment knobs:

```bash
export LANGLY_ZK_DIR=./zettelkasten
export LANGLY_FILE_ROOT=.
export LANGLY_UPLOAD_DIR=./uploads
```

## V2 Quickstart

V2 endpoints are available under `/api/v2`.

Example run:

```bash
curl -s http://localhost:8000/api/v2/workflows/run \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello from v2"}'
```

List runs:

```bash
curl -s http://localhost:8000/api/v2/runs
```

V2 runtime database path:

```bash
export V2_DB_PATH=./runtime_v2.db
```

V2 endpoints are documented in `docs/V2_ENDPOINTS.md`.
Testing strategy: `docs/TESTING_STRATEGY.md`.

## V3 (Experimental)

V3 is a from-scratch, graph-first runtime that uses small specialized models.
It runs in parallel with V2 and does not share state.

Key capabilities:
- **Event-Sourced Storage**: Runs and deltas persisted in async SQLite (`runtime_v3.db`)
- **Small Model Registry**: Role-based model selection with fallbacks (all <=3B)
- **Typed Tools**: Full type safety with schema validation
- **HITL Approvals**: Tool calls can require human approval with resume flow
- **WebSocket Deltas**: Real-time streaming of run updates at `/api/v3/ws/deltas`
- **Minimal Dependencies**: No Neo4j required for V3 runtime

For a comprehensive guide to V3 concepts and design philosophy, see `docs/OVERVIEW.md`.
Architecture: `docs/ARCHITECTURE_V3.md`.
UI status: see “V3 UI Status” in `docs/OVERVIEW.md`.

Example run:

```bash
curl -s http://localhost:8000/api/v3/workflows/run \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello from v3"}'
```

List runs:

```bash
curl -s http://localhost:8000/api/v3/runs
```

V3 runtime database path:

```bash
export V3_DB_PATH=./runtime_v3.db
```

V3 endpoints are documented in `docs/V3_ENDPOINTS.md`.

### V3 API Reference

- `POST /api/v3/workflows/run`
- `GET /api/v3/runs`
- `GET /api/v3/runs/{run_id}`
- `GET /api/v3/runs/{run_id}/deltas`
- `GET /api/v3/tools`
- `POST /api/v3/tools/call`
- `GET /api/v3/hitl/requests`
- `POST /api/v3/hitl/requests/{request_id}/resolve`
- `WS /api/v3/ws/deltas`

## Architecture

### Agent Hierarchy

```
You (Business Owner)
    └── PM Agent (Granite Dense 8B)
            ├── Coder Agent (Granite Code 8B)
            ├── Architect Agent (Granite Dense 8B)
            ├── Tester Agent (Granite Code 3B)
            ├── Reviewer Agent (Granite Dense 8B)
            └── Documentation Agent (Granite Dense 2B)
```

### Project Structure

```
langly/
├── app/
│   ├── __init__.py
│   ├── core/                   # Config, schemas, constants, exceptions
│   ├── agents/                 # Agent implementations
│   ├── graphs/                 # LangGraph workflows (v2)
│   ├── llm/                    # Ollama client, model configs
│   ├── memory/                 # Neo4j stores
│   ├── tools/                  # Tool framework
│   ├── reliability/            # Circuit breaker, health checks
│   ├── hitl/                   # Human-in-the-loop
│   ├── runtime/                # V2 runtime storage + config
│   │   └── tools/              # V2 tool implementations
│   ├── v3/                     # V3 runtime engine + store
│   │   └── tools/              # V3 tool implementations
│   └── api/                    # FastAPI application + routes
│       ├── app.py              # Application factory
│       └── routes/             # Versioned API routers (v1/v2/v3)
├── static/                     # Frontend assets
│   ├── index.html              # Main dashboard
│   ├── tools.html              # Tool management
│   ├── interventions.html      # HITL page
│   ├── api-client.js           # JavaScript API client
│   ├── harness.js/.css         # Chat harness UI
│   ├── panel-system.js/.css    # Draggable panels
│   ├── tiling-manager.js/.css  # Tiling window manager
│   └── git-tree.js/.css        # Git tree panel
├── docs/                       # Architecture + endpoint docs
│   ├── ARCHITECTURE_V2.md
│   ├── ARCHITECTURE_V3.md
│   ├── OVERVIEW.md
│   ├── V2_ENDPOINTS.md
│   └── V3_ENDPOINTS.md
├── tests/                      # Test suite (unit, e2e, v2, v3)
├── pyproject.toml
└── README.md
```

## Model Selection

| Agent | Primary Model | Fallback | Use Case |
|-------|---------------|----------|----------|
| Router | Granite MoE 1B | Granite MoE 3B / Granite Dense 2B | Fast routing decisions |
| PM Agent | Granite Dense 8B | Granite Dense 2B / Granite MoE 3B | Planning, coordination |
| Coder | Granite Code 8B | Granite Code 3B | Code generation |
| Architect | Granite Dense 8B | Granite Dense 2B / Granite MoE 3B | System design |
| Tester | Granite Code 3B | Granite Dense 2B / Granite MoE 3B | Test generation |
| Reviewer | Granite Dense 8B | Granite Dense 2B / Granite MoE 3B | Code review |
| Documentation | Granite Dense 2B | Granite MoE 3B / Granite MoE 1B | Technical writing |
| Safety | Granite Guardian 8B | N/A | Content validation |
| Embeddings | Granite Embedding | N/A | Semantic search |

## API Endpoints

### Summary

- **V1 (legacy)**: `/api/v1/health`, `/api/v1/workflows`, `/api/v1/agents`, `/api/v1/chat`
- **V2 (primary UI/runtime)**: `/api/v2/harness/run`, `/api/v2/workflows/run`, `/api/v2/runs`, `/api/v2/tools`,
  `/api/v2/hitl`, `/api/v2/timeline`, `/api/v2/health/v2`, `/api/v2/overview`, `/api/v2/models`, `/api/v2/ws/deltas`
- **V3 (experimental)**: see “V3 API Reference” above and `docs/V3_ENDPOINTS.md`

Full endpoint lists:
- V2: `docs/V2_ENDPOINTS.md`
- V3: `docs/V3_ENDPOINTS.md`
- Repo overview: `docs/CHANGELOG.md`
- I/O examples: `docs/IO_EXAMPLES.md`

<details>
<summary>V2 Endpoints (full)</summary>

Workflows
- `POST /api/v2/workflows/run`

Runs
- `GET /api/v2/runs`
- `GET /api/v2/runs/{run_id}`
- `GET /api/v2/runs/{run_id}/deltas`

Timeline
- `GET /api/v2/timeline/{run_id}`
- `GET /api/v2/timeline/recent`

Recent
- `GET /api/v2/recent/deltas`

Snapshots
- `GET /api/v2/snapshots/{session_id}`
- `GET /api/v2/snapshots/{session_id}/latest`

HITL
- `POST /api/v2/hitl/requests`
- `GET /api/v2/hitl/requests`
- `GET /api/v2/hitl/requests/{request_id}`
- `POST /api/v2/hitl/requests/{request_id}/resolve`
- `GET /api/v2/hitl/pending-tools`

Events
- `WS /api/v2/ws/deltas`

Health
- `GET /api/v2/health/v2`
- `GET /api/v2/health/ready`
- `GET /api/v2/health/live`

Agents
- `GET /api/v2/agents`
- `GET /api/v2/agents/{role}`

Sessions
- `GET /api/v2/sessions/{session_id}/runs`
- `GET /api/v2/sessions/{session_id}/messages`
- `GET /api/v2/sessions/{session_id}/summary`
- `POST /api/v2/sessions/{session_id}/clear`
- `DELETE /api/v2/sessions/runs/{run_id}`

Dashboard
- `GET /api/v2/dashboard`

Seed
- `POST /api/v2/seed/run`

Status
- `GET /api/v2/status`

Config
- `GET /api/v2/config`

Overview
- `GET /api/v2/overview`

Metrics
- `GET /api/v2/metrics`

Reset
- `POST /api/v2/reset`

Cleanup
- `POST /api/v2/cleanup/prune`

Diagnostics
- `GET /api/v2/diagnostics`

Summary
- `GET /api/v2/summary`

Models
- `GET /api/v2/models`

Neo4j
- `GET /api/v2/neo4j`

Tools
- `GET /api/v2/tools`
- `GET /api/v2/tools/{tool_name}`

Docs
- `GET /api/v2/docs`

Harness
- `POST /api/v2/harness/run`
</details>

### WebSocket
- `WS /ws` - Real-time updates (legacy)
- `WS /api/v2/ws/deltas` - Real-time delta streaming (v2)
- `WS /api/v3/ws/deltas` - Real-time delta streaming (v3)

## Frontend Features

### Dashboard (index.html)
- Agent status panels with real-time updates
- Conversation interface for task input
- Workflow visualization
- Layout controls (grid, horizontal, vertical, master-stack)

### Tools Management (tools.html)
- Category filtering (File System, Code Execution, Version Control, etc.)
- Tool registration with JSON schema editor
- Configuration panel for limits and access controls

### Interventions (interventions.html)
- Pending/resolved intervention list
- Approve/Reject/Request Info actions
- Timeline view for checkpoint history
- State diff comparison for debugging

### Keyboard Shortcuts
| Shortcut | Action |
|----------|--------|
| Alt+1 | Grid layout |
| Alt+2 | Horizontal split |
| Alt+3 | Vertical split |
| Alt+4 | Master-stack layout |
| Alt+Space | Cycle layouts |

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_hitl.py -v
```

Test suites are organized under `tests/unit`, `tests/e2e`, `tests/v2`, and `tests/v3`.

**NixOS**: If uv's downloaded Python fails, use the system Python:

```bash
uv sync --extra dev --python /run/current-system/sw/bin/python3
```

### Code Quality

```bash
# Format code
black app tests

# Lint
ruff check app tests

# Type check
mypy app
```

### Docker Compose

```yaml
version: '3.8'
services:
  langly:
    build: .
    ports:
      - "8000:8000"
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
      - NEO4J_URI=bolt://neo4j:7687
    depends_on:
      - ollama
      - neo4j

  ollama:
    image: ollama/ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama

  neo4j:
    image: neo4j:5-community
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      - NEO4J_AUTH=neo4j/password
    volumes:
      - neo4j_data:/data

volumes:
  ollama_data:
  neo4j_data:
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | langly | Application name |
| `DEBUG` | false | Enable debug mode |
| `LOG_LEVEL` | INFO | Logging level |
| `OLLAMA_BASE_URL` | http://localhost:11434 | Ollama server URL |
| `NEO4J_URI` | bolt://localhost:7687 | Neo4j connection URI |
| `NEO4J_USERNAME` | neo4j | Neo4j username |
| `NEO4J_PASSWORD` | - | Neo4j password |
| `NEO4J_DATABASE` | neo4j | Neo4j database name |
| `API_HOST` | 0.0.0.0 | API server host |
| `API_PORT` | 8000 | API server port |
| `MAX_ITERATIONS` | 50 | Max workflow iterations |
| `WORKFLOW_TIMEOUT` | 300 | Workflow timeout (seconds) |
| `V3_DB_PATH` | ./runtime_v3.db | V3 SQLite database path |
| `ENABLE_NEO4J_MEMORY` | false | Enable Neo4j persistence for v2 summaries |
| `LANGLY_AUTO_TOOLS` | greptile,lint,jj | Auto tools for harness runs |
| `LANGLY_GREPTILE_DIR` | ~/Desktop/greptile | Greptile MCP repo path |

### Circuit Breaker Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | 5 | Failures before open |
| `CIRCUIT_BREAKER_RECOVERY_TIMEOUT` | 30 | Seconds before half-open |
| `CIRCUIT_BREAKER_EXPECTED_EXCEPTIONS` | - | Exception classes to track |

## Production Deployment

### Recommended Setup

1. **ASGI Server**: Use Uvicorn with multiple workers
   ```bash
   uvicorn app.api.app:app --workers 4 --host 0.0.0.0 --port 8000
   ```

2. **Reverse Proxy**: Nginx or Traefik for SSL termination

3. **Neo4j Cluster**: Use Neo4j Aura or self-hosted cluster for HA

4. **Ollama Scaling**: Multiple Ollama instances behind load balancer

5. **Monitoring**: Prometheus + Grafana for metrics

6. **Logging**: Structured logging with ELK stack

## Troubleshooting

### Ollama Connection Failed
```bash
# Check if Ollama is running
ollama list

# Test model availability
ollama run granite3.1-dense:8b "Hello"
```

### Neo4j Connection Issues
```bash
# Check Neo4j status
cypher-shell -u neo4j -p password "RETURN 1"

# Reset database
cypher-shell -u neo4j -p password "MATCH (n) DETACH DELETE n"
```

### Port Already in Use
```bash
# Kill process on port 8000
kill $(lsof -t -i:8000)
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [LangChain](https://langchain.com/) and [LangGraph](https://langchain-ai.github.io/langgraph/) for agent orchestration
- [IBM Granite](https://www.ibm.com/granite) for open-source language models
- [Ollama](https://ollama.ai/) for local model serving
- [Neo4j](https://neo4j.com/) for graph database capabilities
- [FastAPI](https://fastapi.tiangolo.com/) for the API framework
