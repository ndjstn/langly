"""Circuit breaker implementation for fault tolerance.

This module provides circuit breaker pattern implementations for protecting
against cascading failures in distributed agent workflows. Uses pybreaker
for the underlying circuit breaker logic.
"""

import asyncio
import functools
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, TypeVar, ParamSpec

import pybreaker

from app.core.exceptions import CircuitBreakerOpenError, LanglyError

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    """Configuration for a circuit breaker.

    Attributes:
        name: Unique identifier for the circuit breaker.
        fail_max: Number of failures before opening the circuit.
        reset_timeout: Seconds to wait before attempting recovery.
        exclude_exceptions: Exception types that should not trip the breaker.
        include_exceptions: Only these exception types will trip the breaker.
        listeners: Callbacks for state change events.
    """

    name: str = "default"
    fail_max: int = 5
    reset_timeout: float = 30.0
    failure_threshold: int = 5
    success_threshold: int = 3
    timeout: float = 30.0
    exclude_exceptions: tuple[type[Exception], ...] = ()
    include_exceptions: tuple[type[Exception], ...] | None = None
    listeners: list[Any] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Sync legacy fields with fail_max/reset_timeout for compatibility."""
        if self.fail_max == 5 and self.failure_threshold != 5:
            self.fail_max = self.failure_threshold
        if self.reset_timeout == 30.0 and self.timeout != 30.0:
            self.reset_timeout = self.timeout


@dataclass
class CircuitBreakerMetrics:
    """Metrics for a circuit breaker.

    Attributes:
        name: Circuit breaker name.
        state: Current state of the circuit.
        failure_count: Number of consecutive failures.
        success_count: Number of consecutive successes.
        total_failures: Total failures since creation.
        total_successes: Total successes since creation.
        last_failure_time: Timestamp of last failure.
        last_success_time: Timestamp of last success.
        opened_count: Times the circuit has opened.
    """

    name: str
    state: CircuitState
    failure_count: int = 0
    success_count: int = 0
    total_failures: int = 0
    total_successes: int = 0
    last_failure_time: datetime | None = None
    last_success_time: datetime | None = None
    opened_count: int = 0


class CircuitBreaker:
    """Simple circuit breaker for tests/compatibility."""

    def __init__(self, name: str, config: CircuitBreakerConfig | None = None) -> None:
        self.name = name
        self.config = config or CircuitBreakerConfig(name=name)
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self._last_failure_time: datetime | None = None

    def allow_call(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if self._last_failure_time is None:
                return False
            elapsed = (datetime.now() - self._last_failure_time).total_seconds()
            if elapsed >= self.config.timeout:
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                return True
            return False
        return True

    def record_success(self) -> None:
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.reset()
            return
        self.success_count += 1

    def record_failure(self) -> None:
        self.failure_count += 1
        self._last_failure_time = datetime.now()
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            return
        if self.failure_count >= self.config.failure_threshold:
            self.state = CircuitState.OPEN

    def reset(self) -> None:
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self._last_failure_time = None


class CircuitBreakerListener(pybreaker.CircuitBreakerListener):
    """Custom listener for circuit breaker events."""

    def __init__(self, name: str) -> None:
        """Initialize the listener.

        Args:
            name: Name of the circuit breaker.
        """
        self.name = name
        self.opened_count = 0
        self.last_failure_time: datetime | None = None
        self.last_success_time: datetime | None = None

    def before_call(
        self,
        cb: pybreaker.CircuitBreaker,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Called before the protected function is executed.

        Args:
            cb: The circuit breaker instance.
            func: The function being called.
            *args: Positional arguments.
            **kwargs: Keyword arguments.
        """
        logger.debug(f"Circuit breaker '{self.name}' call starting")

    def state_change(
        self,
        cb: pybreaker.CircuitBreaker,
        old_state: pybreaker.CircuitBreakerState | None,
        new_state: pybreaker.CircuitBreakerState,
    ) -> None:
        """Called when the circuit breaker state changes.

        Args:
            cb: The circuit breaker instance.
            old_state: Previous state (may be None on first transition).
            new_state: New state.
        """
        old_name = type(old_state).__name__ if old_state else "None"
        new_name = type(new_state).__name__
        logger.info(
            f"Circuit breaker '{self.name}' state changed: "
            f"{old_name} -> {new_name}"
        )

        if new_name == "CircuitOpenState":
            self.opened_count += 1

    def failure(
        self,
        cb: pybreaker.CircuitBreaker,
        exc: BaseException,
    ) -> None:
        """Called when the protected function fails.

        Args:
            cb: The circuit breaker instance.
            exc: The exception that was raised.
        """
        self.last_failure_time = datetime.utcnow()
        logger.warning(
            f"Circuit breaker '{self.name}' recorded failure: {exc}"
        )

    def success(self, cb: pybreaker.CircuitBreaker) -> None:
        """Called when the protected function succeeds.

        Args:
            cb: The circuit breaker instance.
        """
        self.last_success_time = datetime.utcnow()
        logger.debug(f"Circuit breaker '{self.name}' recorded success")


class ManagedCircuitBreaker:
    """Managed circuit breaker with enhanced features.

    Provides async support, metrics collection, and integration
    with the Langly error handling system.
    """

    def __init__(self, config: CircuitBreakerConfig) -> None:
        """Initialize the managed circuit breaker.

        Args:
            config: Configuration for the circuit breaker.
        """
        self.config = config
        self.listener = CircuitBreakerListener(config.name)

        listeners = [self.listener] + config.listeners

        self._breaker = pybreaker.CircuitBreaker(
            fail_max=config.fail_max,
            reset_timeout=config.reset_timeout,
            exclude=list(config.exclude_exceptions),
            listeners=listeners,
            name=config.name,
        )

        self._total_failures = 0
        self._total_successes = 0
        self._lock = asyncio.Lock()

    @property
    def name(self) -> str:
        """Get the circuit breaker name."""
        return self.config.name

    @property
    def state(self) -> CircuitState:
        """Get the current circuit state."""
        state_name = type(self._breaker.current_state).__name__
        state_map = {
            "CircuitClosedState": CircuitState.CLOSED,
            "CircuitOpenState": CircuitState.OPEN,
            "CircuitHalfOpenState": CircuitState.HALF_OPEN,
        }
        return state_map.get(state_name, CircuitState.CLOSED)

    @property
    def is_closed(self) -> bool:
        """Check if the circuit is closed (normal operation)."""
        return self.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if the circuit is open (failing fast)."""
        return self.state == CircuitState.OPEN

    def get_metrics(self) -> CircuitBreakerMetrics:
        """Get current metrics for the circuit breaker.

        Returns:
            CircuitBreakerMetrics with current state and counts.
        """
        return CircuitBreakerMetrics(
            name=self.name,
            state=self.state,
            failure_count=self._breaker.fail_counter,
            success_count=0,
            total_failures=self._total_failures,
            total_successes=self._total_successes,
            last_failure_time=self.listener.last_failure_time,
            last_success_time=self.listener.last_success_time,
            opened_count=self.listener.opened_count,
        )

    def call(
        self,
        func: Callable[P, R],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> R:
        """Execute a function with circuit breaker protection.

        Args:
            func: The function to execute.
            *args: Positional arguments for the function.
            **kwargs: Keyword arguments for the function.

        Returns:
            The result of the function.

        Raises:
            CircuitBreakerOpenError: If the circuit is open.
            Exception: If the function raises an exception.
        """
        try:
            result = self._breaker.call(func, *args, **kwargs)
            self._total_successes += 1
            return result
        except pybreaker.CircuitBreakerError as e:
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is open",
                circuit_name=self.name,
            ) from e
        except Exception:
            self._total_failures += 1
            raise

    async def call_async(
        self,
        func: Callable[P, R],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> R:
        """Execute an async function with circuit breaker protection.

        Args:
            func: The async function to execute.
            *args: Positional arguments for the function.
            **kwargs: Keyword arguments for the function.

        Returns:
            The result of the function.

        Raises:
            CircuitBreakerOpenError: If the circuit is open.
            Exception: If the function raises an exception.
        """
        async with self._lock:
            if self.is_open:
                remaining = self._get_remaining_timeout()
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is open. "
                    f"Retry in {remaining:.1f}s",
                    circuit_name=self.name,
                )

            try:
                if asyncio.iscoroutinefunction(func):
                    coro_result: Any = await func(*args, **kwargs)
                    result: R = coro_result
                else:
                    sync_result: Any = func(*args, **kwargs)
                    result = sync_result

                self._breaker.call(lambda: None)
                self._total_successes += 1
                return result

            except LanglyError:
                raise
            except Exception as e:
                self._total_failures += 1
                try:
                    self._breaker.call(self._raise_exception, e)
                except pybreaker.CircuitBreakerError:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' opened due to: {e}",
                        circuit_name=self.name,
                    ) from e
                raise

    def _raise_exception(self, exc: Exception) -> None:
        """Helper to raise an exception within the breaker context.

        Args:
            exc: The exception to raise.
        """
        raise exc

    def _get_remaining_timeout(self) -> float:
        """Get remaining time before the circuit attempts to close.

        Returns:
            Remaining seconds until half-open state.
        """
        state = self._breaker.current_state
        if hasattr(state, "_opened"):
            opened_at: float = getattr(state, "_opened", 0.0)
            elapsed = time.time() - opened_at
            remaining = max(0, self.config.reset_timeout - elapsed)
            return remaining
        return 0.0

    def reset(self) -> None:
        """Manually reset the circuit breaker to closed state."""
        self._breaker.close()
        logger.info(f"Circuit breaker '{self.name}' manually reset")

    def trip(self) -> None:
        """Manually trip the circuit breaker to open state."""
        self._breaker.open()
        logger.info(f"Circuit breaker '{self.name}' manually tripped")


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers.

    Provides centralized access to circuit breakers for different
    services and components in the agent system.
    """

    def __init__(self) -> None:
        """Initialize the circuit breaker registry."""
        self._breakers: dict[str, ManagedCircuitBreaker] = {}
        self._simple_breakers: dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()

    def register(
        self,
        config: CircuitBreakerConfig,
    ) -> ManagedCircuitBreaker:
        """Register a new circuit breaker.

        Args:
            config: Configuration for the circuit breaker.

        Returns:
            The registered circuit breaker.

        Raises:
            ValueError: If a breaker with the same name exists.
        """
        if config.name in self._breakers:
            raise ValueError(
                f"Circuit breaker '{config.name}' already registered"
            )

        breaker = ManagedCircuitBreaker(config)
        self._breakers[config.name] = breaker
        logger.info(f"Registered circuit breaker: {config.name}")
        return breaker

    def get(self, name: str) -> ManagedCircuitBreaker | None:
        """Get a circuit breaker by name.

        Args:
            name: The circuit breaker name.

        Returns:
            The circuit breaker or None if not found.
        """
        return self._breakers.get(name)

    def get_or_create(
        self,
        config: CircuitBreakerConfig | str,
    ) -> ManagedCircuitBreaker | CircuitBreaker:
        """Get an existing circuit breaker or create a new one.

        Args:
            config: Configuration for the circuit breaker or name (simple).

        Returns:
            The circuit breaker (existing or new).
        """
        if isinstance(config, str):
            name = config
            if name in self._simple_breakers:
                return self._simple_breakers[name]
            breaker = CircuitBreaker(name=name)
            self._simple_breakers[name] = breaker
            return breaker

        if config.name in self._breakers:
            return self._breakers[config.name]
        return self.register(config)

    def unregister(self, name: str) -> bool:
        """Unregister a circuit breaker.

        Args:
            name: The circuit breaker name.

        Returns:
            True if removed, False if not found.
        """
        if name in self._breakers:
            del self._breakers[name]
            logger.info(f"Unregistered circuit breaker: {name}")
            return True
        return False

    def list_all(self) -> list[str]:
        """List all registered circuit breaker names.

        Returns:
            List of circuit breaker names.
        """
        return list(self._breakers.keys())

    def get_all(self) -> list[CircuitBreaker]:
        """Return all simple circuit breakers (compat)."""
        return list(self._simple_breakers.values())

    def get_states(self) -> dict[str, CircuitState]:
        """Return states for simple circuit breakers (compat)."""
        return {
            name: breaker.state for name, breaker in self._simple_breakers.items()
        }

    def get_all_metrics(self) -> dict[str, CircuitBreakerMetrics]:
        """Get metrics for all registered circuit breakers.

        Returns:
            Dictionary mapping names to metrics.
        """
        return {
            name: breaker.get_metrics()
            for name, breaker in self._breakers.items()
        }

    def reset_all(self) -> None:
        """Reset all circuit breakers to closed state."""
        for breaker in self._breakers.values():
            breaker.reset()
        logger.info("All circuit breakers reset")


_global_registry: CircuitBreakerRegistry | None = None


def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    """Get the global circuit breaker registry.

    Returns:
        The global CircuitBreakerRegistry instance.
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = CircuitBreakerRegistry()
    return _global_registry


def circuit_breaker(
    name: str,
    fail_max: int = 5,
    reset_timeout: float = 30.0,
    exclude_exceptions: tuple[type[Exception], ...] = (),
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to apply circuit breaker protection to a function.

    Args:
        name: Unique name for the circuit breaker.
        fail_max: Number of failures before opening.
        reset_timeout: Seconds before attempting recovery.
        exclude_exceptions: Exceptions that won't trip the breaker.

    Returns:
        Decorated function with circuit breaker protection.
    """
    config = CircuitBreakerConfig(
        name=name,
        fail_max=fail_max,
        reset_timeout=reset_timeout,
        exclude_exceptions=exclude_exceptions,
    )

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        registry = get_circuit_breaker_registry()
        breaker = registry.get_or_create(config)

        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(
                *args: P.args,
                **kwargs: P.kwargs,
            ) -> Any:
                return await breaker.call_async(func, *args, **kwargs)
            return async_wrapper  # type: ignore[return-value]
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
                return breaker.call(func, *args, **kwargs)
            return sync_wrapper

    return decorator


# Pre-defined circuit breakers for common services
DEFAULT_BREAKER_CONFIGS = {
    "ollama": CircuitBreakerConfig(
        name="ollama",
        fail_max=3,
        reset_timeout=60.0,
    ),
    "neo4j": CircuitBreakerConfig(
        name="neo4j",
        fail_max=5,
        reset_timeout=30.0,
    ),
    "external_api": CircuitBreakerConfig(
        name="external_api",
        fail_max=5,
        reset_timeout=45.0,
    ),
    "code_sandbox": CircuitBreakerConfig(
        name="code_sandbox",
        fail_max=3,
        reset_timeout=60.0,
    ),
    "guardian": CircuitBreakerConfig(
        name="guardian",
        fail_max=5,
        reset_timeout=30.0,
    ),
}


def get_default_breaker(name: str) -> ManagedCircuitBreaker:
    """Get a pre-configured circuit breaker for common services.

    Args:
        name: Name of the service (ollama, neo4j, external_api, etc.)

    Returns:
        Configured circuit breaker.

    Raises:
        ValueError: If no default config exists for the name.
    """
    if name not in DEFAULT_BREAKER_CONFIGS:
        raise ValueError(f"No default circuit breaker config for: {name}")

    registry = get_circuit_breaker_registry()
    return registry.get_or_create(DEFAULT_BREAKER_CONFIGS[name])
