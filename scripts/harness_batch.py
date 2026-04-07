#!/usr/bin/env python3
"""Run a batch harness evaluation loop."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx


DEFAULT_PROMPTS = [
    "Summarize the repository's purpose and key modules.",
    "List the top 3 risks in the current architecture.",
    "Propose a testing plan for the harness pipeline.",
    "Explain how tool selection should work for code tasks.",
    "Describe how to integrate MCP browser automation.",
    "What are the key runtime dependencies and why?",
    "Suggest improvements to prompt enhancement pipeline.",
    "Explain how to enforce citations using Searx.",
    "Identify areas where latency can be reduced.",
    "Provide a short roadmap for the next 2 sprints.",
]


def load_prompts(path: str | None) -> list[str]:
    if not path:
        return DEFAULT_PROMPTS
    content = Path(path).read_text(encoding="utf-8").strip().splitlines()
    return [line for line in content if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="http://localhost:8000")
    parser.add_argument("--prompts", help="Path to prompts file")
    parser.add_argument("--grade", action="store_true")
    parser.add_argument("--research", action="store_true")
    parser.add_argument("--citations", action="store_true")
    parser.add_argument("--tuning", action="store_true")
    args = parser.parse_args()

    messages = load_prompts(args.prompts)
    payload = {
        "messages": messages,
        "grade": args.grade or True,
        "research": args.research,
        "citations": args.citations,
        "tuning": args.tuning or True,
    }

    resp = httpx.post(f"{args.host}/api/v2/harness/batch", json=payload, timeout=600)
    resp.raise_for_status()
    data = resp.json()
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
