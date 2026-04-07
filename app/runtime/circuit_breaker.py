"""Simple circuit breaker for runtime calls."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class CircuitBreaker:
    """Consecutive-failure circuit breaker with cooldown."""

    failure_threshold: int = 3
    cooldown_seconds: int = 60
    failures: int = 0
    opened_at: datetime | None = None

    def can_execute(self) -> bool:
        """Return True if the breaker allows execution."""
        if self.opened_at is None:
            return True
        return datetime.utcnow() >= self.opened_at + timedelta(seconds=self.cooldown_seconds)

    def record_success(self) -> None:
        """Reset breaker on success."""
        self.failures = 0
        self.opened_at = None

    def record_failure(self) -> None:
        """Increment failures and open breaker if threshold reached."""
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.opened_at = datetime.utcnow()
