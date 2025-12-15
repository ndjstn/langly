"""Reliability and safety systems for the multi-agent platform.

This package provides reliability infrastructure including:
- Circuit breakers for failure isolation
- Loop detection for workflow monitoring
- Health checks for component monitoring
- Graceful degradation for resilience
"""

from app.reliability.circuit_breaker import (
    CircuitBreakerConfig,
    CircuitBreakerMetrics,
    CircuitBreakerRegistry,
    CircuitState,
    ManagedCircuitBreaker,
    circuit_breaker,
    get_circuit_breaker_registry,
)
from app.reliability.graceful_degradation import (
    DegradationLevel,
    FallbackConfig,
    FeatureFlag,
    FeatureStatus,
    GracefulDegradationManager,
    RateLimiter,
    RateLimitConfig,
    SystemDegradationStatus,
    get_degradation_manager,
)
from app.reliability.health_checks import (
    ComponentHealth,
    ComponentType,
    HealthCheck,
    HealthCheckConfig,
    HealthChecker,
    HealthStatus,
    ProbeResult,
    SystemHealth,
    check_api_health,
    check_memory_health,
    check_neo4j_health,
    check_ollama_health,
    get_health_checker,
    initialize_health_checks,
    liveness_probe,
    readiness_probe,
    shutdown_health_checks,
)
from app.reliability.loop_detection import (
    LoopDetectionConfig,
    LoopDetectionMetrics,
    LoopDetector,
    RecoveryAction,
    RecoveryStrategy,
    StuckCondition,
    StuckConditionHandler,
    TimeoutManager,
    get_loop_detector,
    get_stuck_condition_handler,
    get_timeout_manager,
)

__all__ = [
    # Circuit Breaker
    "CircuitBreakerConfig",
    "CircuitBreakerMetrics",
    "CircuitBreakerRegistry",
    "CircuitState",
    "ManagedCircuitBreaker",
    "circuit_breaker",
    "get_circuit_breaker_registry",
    # Graceful Degradation
    "DegradationLevel",
    "FallbackConfig",
    "FeatureFlag",
    "FeatureStatus",
    "GracefulDegradationManager",
    "RateLimiter",
    "RateLimitConfig",
    "SystemDegradationStatus",
    "get_degradation_manager",
    # Health Checks
    "ComponentHealth",
    "ComponentType",
    "HealthCheck",
    "HealthCheckConfig",
    "HealthChecker",
    "HealthStatus",
    "ProbeResult",
    "SystemHealth",
    "check_api_health",
    "check_memory_health",
    "check_neo4j_health",
    "check_ollama_health",
    "get_health_checker",
    "initialize_health_checks",
    "liveness_probe",
    "readiness_probe",
    "shutdown_health_checks",
    # Loop Detection
    "LoopDetectionConfig",
    "LoopDetectionMetrics",
    "LoopDetector",
    "RecoveryAction",
    "RecoveryStrategy",
    "StuckCondition",
    "StuckConditionHandler",
    "TimeoutManager",
    "get_loop_detector",
    "get_stuck_condition_handler",
    "get_timeout_manager",
]
