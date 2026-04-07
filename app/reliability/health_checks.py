"""Health check system for all platform components.

This module provides a comprehensive health monitoring system for
all components including Ollama, Neo4j, agents, and workflows.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Coroutine

from pydantic import BaseModel

from app.config import get_settings

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health status indicators."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ComponentType(str, Enum):
    """Types of components that can be health-checked."""

    OLLAMA = "ollama"
    NEO4J = "neo4j"
    AGENT = "agent"
    WORKFLOW = "workflow"
    API = "api"
    MEMORY = "memory"
    TOOL = "tool"


@dataclass
class HealthCheckConfig:
    """Configuration for health checks.

    Attributes:
        check_interval: Seconds between health checks.
        timeout_seconds: Timeout for individual checks.
        failure_threshold: Failures before marking unhealthy.
        success_threshold: Successes before marking healthy.
        enable_background_checks: Whether to run background checks.
    """

    check_interval: float = 30.0
    timeout_seconds: float = 10.0
    failure_threshold: int = 3
    success_threshold: int = 2
    enable_background_checks: bool = True


class ComponentHealth(BaseModel):
    """Health status of a single component.

    Attributes:
        name: Component name.
        component_type: Type of component.
        status: Current health status.
        last_check: When the last check occurred.
        response_time_ms: Response time in milliseconds.
        consecutive_failures: Number of consecutive failures.
        consecutive_successes: Number of consecutive successes.
        error_message: Last error message if any.
        details: Additional health details.
    """

    name: str
    component_type: ComponentType | None = None
    status: HealthStatus = HealthStatus.UNKNOWN
    last_check: datetime | None = None
    response_time_ms: float | None = None
    latency_ms: float | None = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    error_message: str | None = None
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}


class SystemHealth(BaseModel):
    """Overall system health status.

    Attributes:
        status: Overall system status.
        components: Health status of all components.
        timestamp: When the check was performed.
        uptime_seconds: How long the system has been running.
        version: Application version.
    """

    status: HealthStatus
    components: list[ComponentHealth]
    timestamp: datetime
    uptime_seconds: float
    version: str = "0.1.0"

    model_config = {"arbitrary_types_allowed": True}


HealthCheckFunc = Callable[[], Coroutine[Any, Any, tuple[bool, dict[str, Any]]]]


@dataclass
class HealthCheck:
    """A registered health check.

    Attributes:
        name: Name of the health check.
        component_type: Type of component being checked.
        check_func: Async function that performs the check.
        critical: Whether this component is critical for system health.
        config: Configuration for this health check.
    """

    name: str
    component_type: ComponentType
    check_func: HealthCheckFunc
    critical: bool = True
    config: HealthCheckConfig = field(default_factory=HealthCheckConfig)


class HealthChecker:
    """Health checker for monitoring system components.

    Maintains a registry of health checks and provides methods
    for checking individual components or the entire system.
    """

    def __init__(self, config: HealthCheckConfig | None = None) -> None:
        """Initialize the health checker.

        Args:
            config: Default configuration for health checks.
        """
        self.config = config or HealthCheckConfig()
        self._checks: dict[str, HealthCheck] = {}
        self._status: dict[str, ComponentHealth] = {}
        self._start_time = datetime.utcnow()
        self._background_task: asyncio.Task[None] | None = None
        self._running = False

    def register(
        self,
        name: str,
        component_type: ComponentType,
        check_func: HealthCheckFunc,
        critical: bool = True,
        config: HealthCheckConfig | None = None,
    ) -> None:
        """Register a health check.

        Args:
            name: Name of the component.
            component_type: Type of component.
            check_func: Async function that returns (healthy, details).
            critical: Whether this component is critical.
            config: Optional custom configuration.
        """
        check = HealthCheck(
            name=name,
            component_type=component_type,
            check_func=check_func,
            critical=critical,
            config=config or self.config,
        )
        self._checks[name] = check
        self._status[name] = ComponentHealth(
            name=name,
            component_type=component_type,
        )
        logger.debug(f"Registered health check: {name}")

    def register_check(
        self,
        name: str,
        check_func: Callable[[], Coroutine[Any, Any, ComponentHealth]],
    ) -> None:
        """Legacy registration helper accepting ComponentHealth return."""
        self.register(
            name=name,
            component_type=ComponentType.API,
            check_func=check_func,
            config=HealthCheckConfig(success_threshold=1, failure_threshold=1),
        )

    def unregister(self, name: str) -> None:
        """Unregister a health check.

        Args:
            name: Name of the component to unregister.
        """
        self._checks.pop(name, None)
        self._status.pop(name, None)
        logger.debug(f"Unregistered health check: {name}")

    async def check_component(self, name: str) -> ComponentHealth:
        """Check health of a single component.

        Args:
            name: Name of the component to check.

        Returns:
            Health status of the component.
        """
        if name not in self._checks:
            return ComponentHealth(
                name=name,
                component_type=ComponentType.API,
                status=HealthStatus.UNKNOWN,
                error_message=f"Unknown component: {name}",
            )

        check = self._checks[name]
        status = self._status[name]
        start_time = time.time()

        try:
            # Run check with timeout
            result = await asyncio.wait_for(
                check.check_func(),
                timeout=check.config.timeout_seconds,
            )

            if isinstance(result, ComponentHealth):
                status = result
                self._status[name] = status
                return status

            healthy, details = result

            response_time = (time.time() - start_time) * 1000

            if healthy:
                status.consecutive_successes += 1
                status.consecutive_failures = 0
                status.error_message = None

                if status.consecutive_successes >= check.config.success_threshold:
                    status.status = HealthStatus.HEALTHY
                else:
                    status.status = HealthStatus.DEGRADED
            else:
                status.consecutive_failures += 1
                status.consecutive_successes = 0
                status.error_message = details.get("error", "Check failed")

                if status.consecutive_failures >= check.config.failure_threshold:
                    status.status = HealthStatus.UNHEALTHY
                else:
                    status.status = HealthStatus.DEGRADED

            status.response_time_ms = response_time
            status.details = details

        except asyncio.TimeoutError:
            status.consecutive_failures += 1
            status.consecutive_successes = 0
            status.status = HealthStatus.UNHEALTHY
            status.error_message = "Health check timed out"
            status.response_time_ms = check.config.timeout_seconds * 1000

        except Exception as e:
            status.consecutive_failures += 1
            status.consecutive_successes = 0
            status.status = HealthStatus.UNHEALTHY
            status.error_message = str(e)
            logger.error(f"Health check failed for {name}: {e}")

        status.last_check = datetime.utcnow()
        return status

    async def check_all(self) -> SystemHealth:
        """Check health of all registered components.

        Returns:
            Overall system health status.
        """
        components: list[ComponentHealth] = []

        # Run all checks concurrently
        tasks = [
            self.check_component(name)
            for name in self._checks
        ]
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, ComponentHealth):
                    components.append(result)
                elif isinstance(result, Exception):
                    logger.error(f"Health check error: {result}")

        # Determine overall status
        overall_status = self._compute_overall_status(components)

        uptime = (datetime.utcnow() - self._start_time).total_seconds()

        return SystemHealth(
            status=overall_status,
            components=components,
            timestamp=datetime.utcnow(),
            uptime_seconds=uptime,
        )

    def _compute_overall_status(
        self,
        components: list[ComponentHealth],
    ) -> HealthStatus:
        """Compute overall system status from component statuses.

        Args:
            components: List of component health statuses.

        Returns:
            Overall system health status.
        """
        if not components:
            return HealthStatus.UNKNOWN

        critical_unhealthy = False
        any_degraded = False
        any_unhealthy = False

        for component in components:
            check = self._checks.get(component.name)
            is_critical = check.critical if check else False

            if component.status == HealthStatus.UNHEALTHY:
                any_unhealthy = True
                if is_critical:
                    critical_unhealthy = True
            elif component.status == HealthStatus.DEGRADED:
                any_degraded = True

        if critical_unhealthy:
            return HealthStatus.UNHEALTHY
        elif any_unhealthy or any_degraded:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY

    async def start_background_checks(self) -> None:
        """Start background health checking."""
        if self._running:
            return

        self._running = True
        self._background_task = asyncio.create_task(
            self._background_check_loop()
        )
        logger.info("Started background health checks")

    async def stop_background_checks(self) -> None:
        """Stop background health checking."""
        self._running = False
        if self._background_task:
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass
            self._background_task = None
        logger.info("Stopped background health checks")

    async def _background_check_loop(self) -> None:
        """Background loop for periodic health checks."""
        while self._running:
            try:
                await self.check_all()
                await asyncio.sleep(self.config.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Background health check error: {e}")
                await asyncio.sleep(5)  # Brief delay on error

    def get_status(self, name: str) -> ComponentHealth | None:
        """Get cached status for a component.

        Args:
            name: Name of the component.

        Returns:
            Cached health status or None.
        """
        return self._status.get(name)

    def get_all_statuses(self) -> dict[str, ComponentHealth]:
        """Get all cached component statuses.

        Returns:
            Dictionary of component name to health status.
        """
        return dict(self._status)


# Built-in health check functions


async def check_ollama_health() -> tuple[bool, dict[str, Any]]:
    """Check Ollama service health.

    Returns:
        Tuple of (healthy, details).
    """
    settings = get_settings()

    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.ollama_host}/api/tags",
                timeout=5.0,
            )
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                return True, {
                    "model_count": len(models),
                    "models": [m.get("name") for m in models[:5]],
                }
            return False, {"error": f"Status code: {response.status_code}"}
    except Exception as e:
        return False, {"error": str(e)}


async def check_neo4j_health() -> tuple[bool, dict[str, Any]]:
    """Check Neo4j service health.

    Returns:
        Tuple of (healthy, details).
    """
    settings = get_settings()

    try:
        from neo4j import AsyncGraphDatabase

        driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

        async with driver.session() as session:
            result = await session.run("RETURN 1 as health")
            record = await result.single()
            await driver.close()

            if record and record["health"] == 1:
                return True, {"connected": True}
            return False, {"error": "Unexpected result"}

    except Exception as e:
        return False, {"error": str(e)}


async def check_api_health() -> tuple[bool, dict[str, Any]]:
    """Check API service health.

    Returns:
        Tuple of (healthy, details).
    """
    # API is healthy if this code is running
    return True, {
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
    }


async def check_memory_health() -> tuple[bool, dict[str, Any]]:
    """Check memory subsystem health.

    Returns:
        Tuple of (healthy, details).
    """
    import psutil

    try:
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        memory_ok = memory.percent < 90
        disk_ok = disk.percent < 90

        return memory_ok and disk_ok, {
            "memory_percent": memory.percent,
            "disk_percent": disk.percent,
            "memory_available_gb": round(memory.available / (1024**3), 2),
            "disk_available_gb": round(disk.free / (1024**3), 2),
        }
    except Exception as e:
        return False, {"error": str(e)}


# Readiness and liveness probe helpers


class ProbeResult(BaseModel):
    """Result of a probe check.

    Attributes:
        ready: Whether the component is ready.
        live: Whether the component is alive.
        message: Optional message.
        details: Additional details.
    """

    ready: bool
    live: bool
    message: str | None = None
    details: dict[str, Any] = {}


async def liveness_probe(checker: HealthChecker) -> ProbeResult:
    """Perform a liveness probe.

    Checks if the application is alive and should not be restarted.

    Args:
        checker: The health checker to use.

    Returns:
        Probe result.
    """
    # Application is live if it can respond
    return ProbeResult(
        ready=True,
        live=True,
        message="Application is alive",
    )


async def readiness_probe(checker: HealthChecker) -> ProbeResult:
    """Perform a readiness probe.

    Checks if the application is ready to accept traffic.

    Args:
        checker: The health checker to use.

    Returns:
        Probe result.
    """
    health = await checker.check_all()

    ready = health.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]

    unhealthy_components = [
        c.name for c in health.components
        if c.status == HealthStatus.UNHEALTHY
    ]

    return ProbeResult(
        ready=ready,
        live=True,
        message=f"System status: {health.status.value}",
        details={
            "status": health.status.value,
            "unhealthy_components": unhealthy_components,
        },
    )


# Global instance management


_health_checker: HealthChecker | None = None


def get_health_checker() -> HealthChecker:
    """Get the global health checker instance.

    Returns:
        The global HealthChecker instance.
    """
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()

        # Register built-in checks
        _health_checker.register(
            "ollama",
            ComponentType.OLLAMA,
            check_ollama_health,
            critical=True,
        )
        _health_checker.register(
            "neo4j",
            ComponentType.NEO4J,
            check_neo4j_health,
            critical=True,
        )
        _health_checker.register(
            "api",
            ComponentType.API,
            check_api_health,
            critical=True,
        )
        _health_checker.register(
            "memory",
            ComponentType.MEMORY,
            check_memory_health,
            critical=False,
        )

    return _health_checker


async def initialize_health_checks(
    enable_background: bool = True,
) -> HealthChecker:
    """Initialize the health check system.

    Args:
        enable_background: Whether to enable background checks.

    Returns:
        The initialized health checker.
    """
    checker = get_health_checker()

    if enable_background:
        await checker.start_background_checks()

    return checker


async def shutdown_health_checks() -> None:
    """Shutdown the health check system."""
    global _health_checker
    if _health_checker:
        await _health_checker.stop_background_checks()
        _health_checker = None
