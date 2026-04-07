"""Structured error types for the v2 runtime."""
from __future__ import annotations

from enum import Enum
from typing import Any


class ErrorKind(str, Enum):
    """Classification of runtime errors."""

    TRANSIENT = "transient"
    RETRYABLE = "retryable"
    PERMANENT = "permanent"
    UNSAFE = "unsafe"


class LanglyError(Exception):
    """Base runtime error with classification metadata."""

    def __init__(
        self,
        message: str,
        *,
        kind: ErrorKind = ErrorKind.RETRYABLE,
        retryable: bool | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.retryable = retryable if retryable is not None else (
            kind in {ErrorKind.TRANSIENT, ErrorKind.RETRYABLE}
        )
        self.details = details or {}

    def as_dict(self) -> dict[str, Any]:
        """Serialize the error for API responses and logs."""
        return {
            "kind": self.kind.value,
            "message": str(self),
            "retryable": self.retryable,
            "details": self.details,
        }
