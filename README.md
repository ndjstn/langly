# Langly Multi-Agent Coding Platform

A production-grade, parallel multi-agent coding platform using LangChain, LangGraph, Pydantic, FastAPI, and Ollama with IBM Granite models.

## Overview

Langly is a hierarchical agent system where you interact as a business owner with a Project Manager agent, who coordinates specialized worker agents including Coder, Code Reviewer, Architect, Tester, and Documentation agents. Each agent operates as an independent node in a LangGraph StateGraph with its own scratchpad, tools, and role-specific prompts.

## Features

- **Hierarchical Multi-Agent Architecture**: PM Agent coordinates Coder, Architect, Tester, Reviewer, and Documentation agents
- **Parallel Execution**: Independent tasks run concurrently using LangGraph's parallel branch nodes
- **IBM Granite Models**: Leverages Granite Dense, MoE, Code, Guardian, and Embedding models via Ollama
- **Graph-Based Memory**: Neo4j stores conversation history, project knowledge, and error patterns
- **Human-in-the-Loop**: Intervention points for approvals, overrides, and time-travel debugging
- **Tool Extensibility**: Dynamic tool registration with file system, code execution, git, and API tools
- **Reliability Systems**: Circuit breaker, loop detection, health checks, and graceful degradation
- **Modern UI**: Draggable panel system with i3-style tiling window management

## Quick Start

### Prerequisites

- Python 3.12+
- [Ollama](https://ollama.ai/) with IBM Granite models
- [Neo4j](https://neo4j.com/) database
- [uv](https://docs.astral.sh/uv/) package manager (recommended)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/langly.git
cd langly

# Install dependencies using uv
uv sync

# Or using pip
pip install -e .
```

### Configure Environment

Create a `.env` file in the project root:

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

### Access the Application

- **Dashboard**: http://localhost:8000/static/index.html
- **Tools Management**: http://localhost:8000/static/tools.html
- **Interventions**: http://localhost:8000/static/interventions.html
- **API Docs**: http://localhost:8000/docs

## Architecture

### Agent Hierarchy

```
You (Business Owner)
    └── PM Agent (Granite Dense 8B)
            ├── Coder Agent (Granite Code 8B)
            ├── Architect Agent (Granite Dense 8B)
            ├── Tester Agent (Granite Code 8B)
            ├── Reviewer Agent (Granite Code 8B)
            └── Documentation Agent (Granite Dense 8B)
```

### Project Structure

```
langly/
├── app/
│   ├── __init__.py
│   ├── core/                   # Config, schemas, constants, exceptions
│   ├── agents/                 # Agent implementations
│   ├── graphs/                 # LangGraph workflows
│   ├── llm/                    # Ollama client, model configs
│   ├── memory/                 # Neo4j stores
│   ├── tools/                  # Tool framework
│   ├── reliability/            # Circuit breaker, health checks
│   ├── hitl/                   # Human-in-the-loop
│   └── api/                    # FastAPI application
├── static/                     # Frontend assets
│   ├── index.html              # Main dashboard
│   ├── tools.html              # Tool management
│   ├── interventions.html      # HITL page
│   ├── api-client.js           # JavaScript API client
│   ├── panel-system.js/.css    # Draggable panels
│   └── tiling-manager.js/.css  # Tiling window manager
├── tests/                      # Test suite
├── pyproject.toml
├── ARCHITECTURE.md             # Detailed architecture docs
└── README.md
```

## Model Selection

| Agent | Primary Model | Fallback | Use Case |
|-------|---------------|----------|----------|
| Router | Granite MoE 3B | Granite Dense 2B | Fast routing decisions |
| PM Agent | Granite Dense 8B | Granite Dense 2B | Planning, coordination |
| Coder | Granite Code 8B | Granite Code 3B | Code generation |
| Architect | Granite Dense 8B | Granite Dense 2B | System design |
| Tester | Granite Code 8B | Granite Code 3B | Test generation |
| Reviewer | Granite Code 8B | Granite Code 3B | Code review |
| Documentation | Granite Dense 8B | Granite Dense 2B | Technical writing |
| Safety | Granite Guardian 8B | N/A | Content validation |
| Embeddings | Granite Embedding | N/A | Semantic search |

## API Endpoints

### Health
- `GET /health` - System health status
- `GET /health/ready` - Readiness check
- `GET /health/live` - Liveness probe

### Tasks
- `POST /api/v1/tasks` - Create a new task
- `GET /api/v1/tasks/{task_id}` - Get task details
- `GET /api/v1/tasks` - List tasks
- `PUT /api/v1/tasks/{task_id}` - Update task
- `DELETE /api/v1/tasks/{task_id}` - Cancel task

### Workflows
- `POST /api/v1/workflows` - Create workflow
- `GET /api/v1/workflows/{workflow_id}` - Get workflow
- `POST /api/v1/workflows/{workflow_id}/pause` - Pause workflow
- `POST /api/v1/workflows/{workflow_id}/resume` - Resume workflow

### Agents
- `GET /api/v1/agents` - List agents
- `GET /api/v1/agents/{agent_id}` - Get agent
- `GET /api/v1/agents/{agent_id}/state` - Get agent state
- `GET /api/v1/agents/{agent_id}/metrics` - Get agent metrics

### Tools
- `GET /api/v1/tools` - List tools
- `POST /api/v1/tools` - Register tool
- `PUT /api/v1/tools/{tool_id}` - Update tool
- `DELETE /api/v1/tools/{tool_id}` - Delete tool
- `POST /api/v1/tools/{tool_id}/execute` - Execute tool

### HITL
- `GET /api/v1/interventions` - List interventions
- `POST /api/v1/interventions/{id}/approve` - Approve
- `POST /api/v1/interventions/{id}/reject` - Reject

### Checkpoints (Time-Travel)
- `GET /api/v1/checkpoints` - List checkpoints
- `POST /api/v1/checkpoints` - Create checkpoint
- `POST /api/v1/checkpoints/{id}/rollback` - Rollback

### WebSocket
- `WS /ws` - Real-time updates

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

### Code Quality

```bash
# Format code
black app tests

# Lint
flake8 app tests

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
