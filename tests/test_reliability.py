"""Unit tests for reliability system components.

Tests for circuit breaker, loop detection, health checks, and graceful
degradation.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.reliability.circuit_breaker import (
    CircuitState,
    CircuitBreakerConfig,
    CircuitBreaker,
    CircuitBreakerRegistry,
)
from app.reliability.loop_detection import (
    LoopType,
    LoopSeverity,
    LoopEvent,
    LoopDetectionConfig,
    LoopDetector,
)
from app.reliability.health_checks import (
    HealthStatus,
    ComponentHealth,
    SystemHealth,
    HealthChecker,
)
from app.reliability.graceful_degradation import (
    DegradationLevel,
    DegradationTrigger,
    DegradationConfig,
    DegradationManager,
)


# =============================================================================
# Circuit Breaker Tests
# =============================================================================


class TestCircuitBreakerConfig:
    """Tests for CircuitBreakerConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = CircuitBreakerConfig()

        assert config.failure_threshold == 5
        assert config.success_threshold == 3
        assert config.timeout == 30.0

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = CircuitBreakerConfig(
            failure_threshold=10,
            success_threshold=5,
            timeout=60.0,
        )

        assert config.failure_threshold == 10
        assert config.success_threshold == 5
        assert config.timeout == 60.0


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    @pytest.fixture
    def breaker(self) -> CircuitBreaker:
        """Create a test circuit breaker."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout=5.0,
        )
        return CircuitBreaker(name="test-breaker", config=config)

    def test_initial_state_closed(self, breaker: CircuitBreaker) -> None:
        """Test initial state is closed."""
        assert breaker.state == CircuitState.CLOSED

    def test_record_success(self, breaker: CircuitBreaker) -> None:
        """Test recording successful call."""
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.success_count == 1

    def test_record_failure_opens_circuit(
        self, breaker: CircuitBreaker
    ) -> None:
        """Test failures open the circuit."""
        # Record failures up to threshold
        for _ in range(3):
            breaker.record_failure()

        assert breaker.state == CircuitState.OPEN

    def test_circuit_allows_call_when_closed(
        self, breaker: CircuitBreaker
    ) -> None:
        """Test closed circuit allows calls."""
        assert breaker.allow_call() is True

    def test_circuit_denies_call_when_open(
        self, breaker: CircuitBreaker
    ) -> None:
        """Test open circuit denies calls."""
        # Open the circuit
        for _ in range(3):
            breaker.record_failure()

        assert breaker.allow_call() is False

    def test_circuit_half_open_after_timeout(
        self, breaker: CircuitBreaker
    ) -> None:
        """Test circuit becomes half-open after timeout."""
        # Open the circuit
        for _ in range(3):
            breaker.record_failure()

        # Simulate timeout by manipulating internal state
        breaker._last_failure_time = (
            datetime.now() - timedelta(seconds=10)
        )

        # Check if call is allowed (triggers half-open)
        assert breaker.allow_call() is True
        assert breaker.state == CircuitState.HALF_OPEN

    def test_half_open_success_closes_circuit(
        self, breaker: CircuitBreaker
    ) -> None:
        """Test successful calls in half-open close the circuit."""
        # Open circuit
        for _ in range(3):
            breaker.record_failure()

        # Transition to half-open
        breaker._last_failure_time = (
            datetime.now() - timedelta(seconds=10)
        )
        breaker.allow_call()

        # Record successes
        breaker.record_success()
        breaker.record_success()

        assert breaker.state == CircuitState.CLOSED

    def test_half_open_failure_reopens_circuit(
        self, breaker: CircuitBreaker
    ) -> None:
        """Test failure in half-open reopens circuit."""
        # Open circuit
        for _ in range(3):
            breaker.record_failure()

        # Transition to half-open
        breaker._last_failure_time = (
            datetime.now() - timedelta(seconds=10)
        )
        breaker.allow_call()

        # Record failure
        breaker.record_failure()

        assert breaker.state == CircuitState.OPEN

    def test_reset(self, breaker: CircuitBreaker) -> None:
        """Test resetting the circuit breaker."""
        # Open circuit
        for _ in range(3):
            breaker.record_failure()

        breaker.reset()

        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0


class TestCircuitBreakerRegistry:
    """Tests for CircuitBreakerRegistry."""

    @pytest.fixture
    def registry(self) -> CircuitBreakerRegistry:
        """Create a test registry."""
        return CircuitBreakerRegistry()

    def test_get_or_create(self, registry: CircuitBreakerRegistry) -> None:
        """Test getting or creating circuit breakers."""
        breaker1 = registry.get_or_create("service-a")
        breaker2 = registry.get_or_create("service-a")

        # Should return same instance
        assert breaker1 is breaker2

    def test_get_all(self, registry: CircuitBreakerRegistry) -> None:
        """Test getting all circuit breakers."""
        registry.get_or_create("service-a")
        registry.get_or_create("service-b")

        all_breakers = registry.get_all()
        assert len(all_breakers) == 2

    def test_get_states(self, registry: CircuitBreakerRegistry) -> None:
        """Test getting circuit breaker states."""
        registry.get_or_create("service-a")
        registry.get_or_create("service-b")

        states = registry.get_states()

        assert "service-a" in states
        assert "service-b" in states


# =============================================================================
# Loop Detection Tests
# =============================================================================


class TestLoopEvent:
    """Tests for LoopEvent model."""

    def test_create_event(self) -> None:
        """Test creating a loop event."""
        event = LoopEvent(
            workflow_id="test-workflow",
            loop_type=LoopType.INFINITE_LOOP,
            severity=LoopSeverity.HIGH,
            description="Detected infinite loop",
        )

        assert event.event_id is not None
        assert event.workflow_id == "test-workflow"
        assert event.loop_type == LoopType.INFINITE_LOOP


class TestLoopDetector:
    """Tests for LoopDetector class."""

    @pytest.fixture
    def detector(self) -> LoopDetector:
        """Create a test loop detector."""
        config = LoopDetectionConfig(
            max_iterations=10,
            state_repeat_threshold=3,
            timeout_seconds=30.0,
        )
        return LoopDetector(config=config)

    def test_record_iteration(self, detector: LoopDetector) -> None:
        """Test recording iterations."""
        detector.record_iteration(
            workflow_id="test-workflow",
            agent_id="coder",
            state_hash="hash1",
        )

        assert detector.get_iteration_count("test-workflow") == 1

    def test_detect_max_iterations(self, detector: LoopDetector) -> None:
        """Test detecting max iteration loop."""
        for i in range(11):
            detector.record_iteration(
                workflow_id="test-workflow",
                agent_id="coder",
                state_hash=f"hash{i}",
            )

        event = detector.check_for_loops("test-workflow")
        assert event is not None
        assert event.loop_type == LoopType.INFINITE_LOOP

    def test_detect_state_repeat(self, detector: LoopDetector) -> None:
        """Test detecting state repetition loop."""
        # Record same state multiple times
        for _ in range(4):
            detector.record_iteration(
                workflow_id="test-workflow",
                agent_id="coder",
                state_hash="same_hash",
            )

        event = detector.check_for_loops("test-workflow")
        assert event is not None
        assert event.loop_type == LoopType.STATE_REPEAT

    def test_no_loop_detected(self, detector: LoopDetector) -> None:
        """Test no loop when conditions not met."""
        detector.record_iteration(
            workflow_id="test-workflow",
            agent_id="coder",
            state_hash="hash1",
        )
        detector.record_iteration(
            workflow_id="test-workflow",
            agent_id="coder",
            state_hash="hash2",
        )

        event = detector.check_for_loops("test-workflow")
        assert event is None

    def test_clear_workflow(self, detector: LoopDetector) -> None:
        """Test clearing workflow state."""
        detector.record_iteration(
            workflow_id="test-workflow",
            agent_id="coder",
            state_hash="hash1",
        )

        detector.clear_workflow("test-workflow")

        assert detector.get_iteration_count("test-workflow") == 0


# =============================================================================
# Health Check Tests
# =============================================================================


class TestHealthStatus:
    """Tests for HealthStatus enum."""

    def test_health_statuses(self) -> None:
        """Test health status values."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"


class TestComponentHealth:
    """Tests for ComponentHealth model."""

    def test_create_healthy_component(self) -> None:
        """Test creating healthy component."""
        health = ComponentHealth(
            name="ollama",
            status=HealthStatus.HEALTHY,
            latency_ms=50.0,
        )

        assert health.status == HealthStatus.HEALTHY
        assert health.latency_ms == 50.0

    def test_create_unhealthy_component(self) -> None:
        """Test creating unhealthy component."""
        health = ComponentHealth(
            name="neo4j",
            status=HealthStatus.UNHEALTHY,
            error="Connection refused",
        )

        assert health.status == HealthStatus.UNHEALTHY
        assert health.error == "Connection refused"


class TestHealthChecker:
    """Tests for HealthChecker class."""

    @pytest.fixture
    def checker(self) -> HealthChecker:
        """Create a test health checker."""
        return HealthChecker()

    @pytest.mark.asyncio
    async def test_check_component_healthy(
        self, checker: HealthChecker
    ) -> None:
        """Test checking a healthy component."""
        # Mock a healthy check function
        async def healthy_check() -> ComponentHealth:
            return ComponentHealth(
                name="test",
                status=HealthStatus.HEALTHY,
                latency_ms=10.0,
            )

        checker.register_check("test", healthy_check)
        health = await checker.check_component("test")

        assert health.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_check_component_unhealthy(
        self, checker: HealthChecker
    ) -> None:
        """Test checking an unhealthy component."""
        async def unhealthy_check() -> ComponentHealth:
            raise ConnectionError("Connection failed")

        checker.register_check("test", unhealthy_check)
        health = await checker.check_component("test")

        assert health.status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_check_all(self, checker: HealthChecker) -> None:
        """Test checking all components."""
        async def check1() -> ComponentHealth:
            return ComponentHealth(
                name="comp1",
                status=HealthStatus.HEALTHY,
            )

        async def check2() -> ComponentHealth:
            return ComponentHealth(
                name="comp2",
                status=HealthStatus.DEGRADED,
            )

        checker.register_check("comp1", check1)
        checker.register_check("comp2", check2)

        result = await checker.check_all()

        assert len(result.components) == 2

    @pytest.mark.asyncio
    async def test_system_health_aggregation(
        self, checker: HealthChecker
    ) -> None:
        """Test system health is aggregated correctly."""
        async def healthy() -> ComponentHealth:
            return ComponentHealth(
                name="healthy",
                status=HealthStatus.HEALTHY,
            )

        async def degraded() -> ComponentHealth:
            return ComponentHealth(
                name="degraded",
                status=HealthStatus.DEGRADED,
            )

        checker.register_check("healthy", healthy)
        checker.register_check("degraded", degraded)

        result = await checker.check_all()

        # Overall status should be DEGRADED
        assert result.status == HealthStatus.DEGRADED


# =============================================================================
# Graceful Degradation Tests
# =============================================================================


class TestDegradationLevel:
    """Tests for DegradationLevel enum."""

    def test_degradation_levels(self) -> None:
        """Test degradation level values."""
        assert DegradationLevel.NORMAL.value == "normal"
        assert DegradationLevel.REDUCED.value == "reduced"
        assert DegradationLevel.MINIMAL.value == "minimal"
        assert DegradationLevel.EMERGENCY.value == "emergency"


class TestDegradationConfig:
    """Tests for DegradationConfig."""

    def test_default_config(self) -> None:
        """Test default configuration."""
        config = DegradationConfig()

        assert config.enable_auto_degradation is True

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = DegradationConfig(
            enable_auto_degradation=False,
            reduced_timeout_multiplier=0.5,
        )

        assert config.enable_auto_degradation is False
        assert config.reduced_timeout_multiplier == 0.5


class TestDegradationManager:
    """Tests for DegradationManager class."""

    @pytest.fixture
    def manager(self) -> DegradationManager:
        """Create a test degradation manager."""
        return DegradationManager()

    def test_initial_level_normal(
        self, manager: DegradationManager
    ) -> None:
        """Test initial degradation level is normal."""
        assert manager.current_level == DegradationLevel.NORMAL

    def test_set_level(self, manager: DegradationManager) -> None:
        """Test setting degradation level."""
        manager.set_level(DegradationLevel.REDUCED)
        assert manager.current_level == DegradationLevel.REDUCED

    def test_escalate(self, manager: DegradationManager) -> None:
        """Test escalating degradation level."""
        manager.escalate()
        assert manager.current_level == DegradationLevel.REDUCED

        manager.escalate()
        assert manager.current_level == DegradationLevel.MINIMAL

        manager.escalate()
        assert manager.current_level == DegradationLevel.EMERGENCY

        # Should stay at emergency
        manager.escalate()
        assert manager.current_level == DegradationLevel.EMERGENCY

    def test_deescalate(self, manager: DegradationManager) -> None:
        """Test de-escalating degradation level."""
        manager.set_level(DegradationLevel.EMERGENCY)

        manager.deescalate()
        assert manager.current_level == DegradationLevel.MINIMAL

        manager.deescalate()
        assert manager.current_level == DegradationLevel.REDUCED

        manager.deescalate()
        assert manager.current_level == DegradationLevel.NORMAL

        # Should stay at normal
        manager.deescalate()
        assert manager.current_level == DegradationLevel.NORMAL

    def test_get_adjusted_timeout(
        self, manager: DegradationManager
    ) -> None:
        """Test timeout adjustment based on level."""
        base_timeout = 60.0

        # Normal level - no change
        timeout = manager.get_adjusted_timeout(base_timeout)
        assert timeout == 60.0

        # Reduced level - shorter timeout
        manager.set_level(DegradationLevel.REDUCED)
        timeout = manager.get_adjusted_timeout(base_timeout)
        assert timeout < 60.0

    def test_get_feature_availability(
        self, manager: DegradationManager
    ) -> None:
        """Test feature availability based on level."""
        # Normal level - all features available
        assert manager.is_feature_available("code_execution") is True
        assert manager.is_feature_available("parallel_tasks") is True

        # Reduced level - some features limited
        manager.set_level(DegradationLevel.REDUCED)
        assert manager.is_feature_available("code_execution") is True

        # Emergency level - minimal features
        manager.set_level(DegradationLevel.EMERGENCY)
        assert manager.is_feature_available("parallel_tasks") is False

    def test_trigger_degradation(
        self, manager: DegradationManager
    ) -> None:
        """Test triggering degradation based on conditions."""
        trigger = DegradationTrigger(
            trigger_type="error_rate",
            threshold=0.5,
            action_level=DegradationLevel.REDUCED,
        )

        manager.add_trigger(trigger)

        # Simulate high error rate
        manager.record_metric("error_rate", 0.6)

        # Should auto-escalate to reduced
        manager.evaluate_triggers()
        assert manager.current_level == DegradationLevel.REDUCED

    def test_reset(self, manager: DegradationManager) -> None:
        """Test resetting to normal level."""
        manager.set_level(DegradationLevel.EMERGENCY)
        manager.reset()
        assert manager.current_level == DegradationLevel.NORMAL


# =============================================================================
# Integration Tests
# =============================================================================


class TestReliabilityIntegration:
    """Integration tests for reliability components."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_with_health_check(self) -> None:
        """Test circuit breaker affects health check status."""
        registry = CircuitBreakerRegistry()
        checker = HealthChecker()

        # Create a circuit breaker
        breaker = registry.get_or_create("test-service")

        # Register health check that considers circuit breaker
        async def service_check() -> ComponentHealth:
            if breaker.state == CircuitState.OPEN:
                return ComponentHealth(
                    name="test-service",
                    status=HealthStatus.UNHEALTHY,
                    error="Circuit breaker open",
                )
            return ComponentHealth(
                name="test-service",
                status=HealthStatus.HEALTHY,
            )

        checker.register_check("test-service", service_check)

        # Initial check should be healthy
        health = await checker.check_component("test-service")
        assert health.status == HealthStatus.HEALTHY

        # Open the circuit
        for _ in range(5):
            breaker.record_failure()

        # Check should now be unhealthy
        health = await checker.check_component("test-service")
        assert health.status == HealthStatus.UNHEALTHY

    def test_loop_detection_triggers_degradation(self) -> None:
        """Test loop detection triggers degradation."""
        detector = LoopDetector()
        manager = DegradationManager()

        # Configure trigger
        trigger = DegradationTrigger(
            trigger_type="loop_detected",
            threshold=1,  # Single loop triggers
            action_level=DegradationLevel.REDUCED,
        )
        manager.add_trigger(trigger)

        # Simulate loop detection
        for _ in range(15):  # Exceed max iterations
            detector.record_iteration(
                workflow_id="test",
                agent_id="coder",
                state_hash="same",
            )

        event = detector.check_for_loops("test")

        if event:
            manager.record_metric("loop_detected", 1)
            manager.evaluate_triggers()

        assert manager.current_level == DegradationLevel.REDUCED
