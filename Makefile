# =============================================================================
# Langly Makefile - Development Automation
# =============================================================================
# Common development tasks for the Langly Multi-Agent Platform
#
# Usage:
#   make help          - Show available commands
#   make install       - Install all dependencies
#   make lint          - Run linting checks
#   make test          - Run all tests
#   make run           - Start the application
# =============================================================================

.PHONY: help install install-dev lint lint-fix format typecheck security test \
        test-unit test-integration test-e2e test-user test-api coverage \
        run run-dev clean docs pre-commit pre-commit-install \
        docker-build docker-run neo4j ollama

# Default target
.DEFAULT_GOAL := help

# =============================================================================
# Help
# =============================================================================

help: ## Show this help message
	@echo "Langly Multi-Agent Platform - Development Commands"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"; printf "\033[36m%-20s\033[0m %s\n", "Target", "Description"} \
		/^[a-zA-Z_-]+:.*?##/ { printf "\033[36m%-20s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# =============================================================================
# Installation
# =============================================================================

install: ## Install production dependencies
	uv sync

install-dev: ## Install all dependencies including dev
	uv sync --all-extras
	uv run pre-commit install

# =============================================================================
# Linting & Formatting
# =============================================================================

lint: ## Run all linting checks
	./scripts/lint.sh

lint-fix: ## Run linting with auto-fix
	./scripts/lint.sh --fix

format: ## Format code with ruff and black
	uv run ruff format .
	uv run ruff check --fix .

typecheck: ## Run type checking with mypy
	uv run mypy app/ --ignore-missing-imports

security: ## Run security scans
	uv run bandit -r app/ -c pyproject.toml -q
	uv run safety check 2>/dev/null || true

# =============================================================================
# Testing
# =============================================================================

test: ## Run all tests
	./scripts/test.sh --coverage

test-unit: ## Run unit tests only
	./scripts/test.sh --unit

test-integration: ## Run integration tests
	./scripts/test.sh --integration

test-e2e: ## Run end-to-end tests
	./scripts/test.sh --e2e

test-user: ## Run automated user flow tests
	./scripts/test.sh --user

test-api: ## Run API endpoint tests
	./scripts/test.sh --api

test-fast: ## Run fast tests (no slow tests)
	./scripts/test.sh --fast --unit

coverage: ## Generate coverage report
	./scripts/test.sh --coverage --html
	@echo "Coverage report: htmlcov/index.html"

# =============================================================================
# Running the Application
# =============================================================================

run: ## Start the application
	./run.sh

run-dev: ## Start in development mode with auto-reload
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-prod: ## Start in production mode
	uv run gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker \
		--bind 0.0.0.0:8000 --access-logfile - --error-logfile -

# =============================================================================
# Pre-commit Hooks
# =============================================================================

pre-commit: ## Run pre-commit on all files
	uv run pre-commit run --all-files

pre-commit-install: ## Install pre-commit hooks
	uv run pre-commit install
	uv run pre-commit install --hook-type commit-msg

pre-commit-update: ## Update pre-commit hooks
	uv run pre-commit autoupdate

# =============================================================================
# Documentation
# =============================================================================

docs: ## Generate API documentation
	@echo "Generating API docs..."
	uv run python -c "from app.main import app; import json; print(json.dumps(app.openapi(), indent=2))" > docs/openapi.json
	@echo "OpenAPI schema saved to docs/openapi.json"

# =============================================================================
# Cleanup
# =============================================================================

clean: ## Clean build artifacts and cache
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf dist/
	rm -rf build/
	rm -rf *.egg-info/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@echo "Cleaned build artifacts and caches"

clean-all: clean ## Clean everything including venv
	rm -rf .venv/
	@echo "Cleaned virtual environment"

# =============================================================================
# External Services
# =============================================================================

neo4j: ## Start Neo4j database with Docker
	docker run -d \
		--name langly-neo4j \
		-p 7474:7474 -p 7687:7687 \
		-e NEO4J_AUTH=neo4j/langly_password \
		-e NEO4J_PLUGINS='["apoc"]' \
		neo4j:5.15
	@echo "Neo4j started at http://localhost:7474"

neo4j-stop: ## Stop Neo4j container
	docker stop langly-neo4j && docker rm langly-neo4j

ollama: ## Pull required Ollama models
	ollama pull granite3.1-dense:2b
	ollama pull granite3.1-dense:8b
	ollama pull granite3.1-moe:1b
	ollama pull granite-code:8b
	ollama pull granite-embedding:278m
	@echo "Ollama models pulled successfully"

ollama-start: ## Start Ollama server
	ollama serve &
	@echo "Ollama server started"

# =============================================================================
# Docker
# =============================================================================

docker-build: ## Build Docker image
	docker build -t langly:latest .

docker-run: ## Run Docker container
	docker run -d \
		--name langly \
		-p 8000:8000 \
		-e NEO4J_URI=bolt://host.docker.internal:7687 \
		-e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
		langly:latest
	@echo "Langly running at http://localhost:8000"

docker-stop: ## Stop Docker container
	docker stop langly && docker rm langly

docker-compose-up: ## Start all services with docker-compose
	docker-compose up -d
	@echo "All services started"

docker-compose-down: ## Stop all services
	docker-compose down

# =============================================================================
# Development Utilities
# =============================================================================

shell: ## Open Python shell with app context
	uv run python -i -c "from app.main import app; print('App loaded. Use app object.')"

check: lint typecheck security ## Run all checks (lint, typecheck, security)

ci: check test ## Run full CI pipeline locally
	@echo "CI pipeline completed successfully"

release-check: ## Check if ready for release
	@echo "Checking release readiness..."
	./scripts/lint.sh --strict
	./scripts/test.sh --coverage
	@echo "Release checks passed!"

# =============================================================================
# Quick Commands
# =============================================================================

dev: install-dev pre-commit-install ## Setup development environment
	@echo "Development environment ready!"

quick-test: ## Quick smoke test
	uv run pytest tests/ -x -q --tb=short -m "not slow and not requires_ollama and not requires_neo4j"

watch-test: ## Run tests in watch mode
	uv run ptw tests/ -- -x -q --tb=short
