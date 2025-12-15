"""
Langly - Multi-Agent Coding Platform.

This package contains the core application components for the parallel
multi-agent coding platform built with LangChain, LangGraph, Pydantic,
FastAPI, and Ollama with IBM Granite models.

Modules:
    api: FastAPI routes and WebSocket handlers
    core: Pydantic schemas, exceptions, and constants
    agents: Agent implementations (PM, Coder, Architect, etc.)
    graphs: LangGraph StateGraph workflows and nodes
    llm: Ollama client and IBM Granite model integrations
    memory: Neo4j memory stores and semantic retrieval
    tools: Extensible tool registry and implementations
    reliability: Circuit breakers, loop detection, timeouts
    hitl: Human-in-the-loop intervention and approval systems
"""

__version__ = "0.1.0"
__author__ = "Langly Team"
