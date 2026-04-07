"""Mermaid graph builder for harness traces."""
from __future__ import annotations

from typing import Any


def build_mermaid_graph(
    message: str,
    scope: dict[str, Any],
    tools: list[dict[str, Any]],
    response: str,
    iterations: int | None = None,
    recovery: bool | None = None,
    research: bool | None = None,
    tuning: bool | None = None,
    keywords: list[str] | None = None,
) -> str:
    nodes = ["U[User Input]", "S[Scope]"]
    edges = ["U --> S"]

    chain_end = "R"
    response_node = "R"
    if iterations and iterations > 1:
        for idx in range(1, iterations + 1):
            nodes.append(f"I{idx}[Iteration {idx}]")
        nodes.append("R[Response]")
        edges.append("S --> I1")
        for idx in range(1, iterations):
            edges.append(f"I{idx} --> I{idx + 1}")
        edges.append(f"I{iterations} --> R")
        chain_end = "I1"
    else:
        nodes.append("R[Response]")
        edges.append("S --> R")
    tool_nodes = []
    for idx, tool in enumerate(tools, start=1):
        name = tool.get("name", f"tool_{idx}")
        node_id = f"T{idx}[{name}]"
        tool_nodes.append(node_id)
        edges.append(f"S --> T{idx}")
        edges.append(f"T{idx} --> {chain_end}")
    if keywords:
        for idx, keyword in enumerate(keywords, start=1):
            safe = str(keyword).replace("[", "(").replace("]", ")")
            nodes.append(f"K{idx}[{safe}]")
            edges.append(f"S --> K{idx}")
            edges.append(f"K{idx} --> {chain_end}")
    if recovery:
        nodes.append("J[JJ Recovery]")
        edges.append("S --> J")
        edges.append(f"J --> {chain_end}")
    if research:
        nodes.append("Q[Research]")
        edges.append("S --> Q")
        edges.append(f"Q --> {chain_end}")
    if tuning:
        nodes.append("TU[Tuning]")
        edges.append(f"{response_node} --> TU")
    lines = ["graph TD"]
    lines.extend(nodes)
    lines.extend(tool_nodes)
    lines.extend(edges)
    return "\n".join(lines)
