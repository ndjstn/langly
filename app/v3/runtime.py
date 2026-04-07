"""Singleton access for V3 runtime components."""
from __future__ import annotations

from app.v3.engine import V3Engine


_engine: V3Engine | None = None


def get_engine() -> V3Engine:
    global _engine
    if _engine is None:
        _engine = V3Engine()
    return _engine
