#!/bin/bash
# Langly Multi-Agent Platform - One-Command Startup Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting Langly Multi-Agent Platform...${NC}"

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}Installing uv package manager...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.local/bin/env
fi

# Sync dependencies
echo -e "${GREEN}📦 Syncing dependencies...${NC}"
uv sync

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo -e "${GREEN}📝 Creating .env file...${NC}"
    cat > .env << 'EOF'
APP_NAME=langly
DEBUG=true
LOG_LEVEL=DEBUG
OLLAMA_BASE_URL=http://localhost:11434
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password123
NEO4J_DATABASE=neo4j
API_HOST=0.0.0.0
API_PORT=8000
MAX_ITERATIONS=50
WORKFLOW_TIMEOUT=300
EOF
fi

# Check if Ollama is running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Ollama is not running. Starting Ollama...${NC}"
    if command -v ollama &> /dev/null; then
        ollama serve &
        sleep 3
    else
        echo -e "${RED}❌ Ollama is not installed. Please install from https://ollama.ai${NC}"
        echo -e "${YELLOW}   The app will still run but LLM features won't work.${NC}"
    fi
fi

# Check for required models (don't block startup)
echo -e "${GREEN}🤖 Checking Ollama models (pulling in background if needed)...${NC}"
if command -v ollama &> /dev/null; then
    # Pull models in background if they don't exist
    (ollama pull granite3.1-dense:2b 2>/dev/null || true) &
fi

# Check if Neo4j is running
if ! curl -s http://localhost:7474 > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Neo4j is not running.${NC}"
    if command -v docker &> /dev/null; then
        echo -e "${GREEN}🐳 Starting Neo4j via Docker...${NC}"
        docker rm -f langly-neo4j 2>/dev/null || true
        docker run -d \
            --name langly-neo4j \
            -p 7474:7474 \
            -p 7687:7687 \
            -e NEO4J_AUTH=neo4j/password123 \
            neo4j:5-community
        echo -e "${YELLOW}⏳ Waiting for Neo4j to start (30s)...${NC}"
        sleep 30
    else
        echo -e "${YELLOW}   Docker not available. Neo4j features may not work.${NC}"
    fi
fi

# Start the FastAPI server
echo -e "${GREEN}🌐 Starting FastAPI server...${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}📍 Dashboard:      http://localhost:8000/static/index.html${NC}"
echo -e "${GREEN}📍 Tools:          http://localhost:8000/static/tools.html${NC}"
echo -e "${GREEN}📍 Interventions:  http://localhost:8000/static/interventions.html${NC}"
echo -e "${GREEN}📍 API Docs:       http://localhost:8000/docs${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Run uvicorn
uv run uvicorn app.api.app:app --reload --host 0.0.0.0 --port 8000
