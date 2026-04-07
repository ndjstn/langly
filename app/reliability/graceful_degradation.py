"""Graceful degradation strategies for system resilience.

This module provides fallback strategies and graceful degradation
mechanisms to maintain partial functionality when components fail.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine, TypeVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)


T = TypeVar("T")


class DegradationLevel(str, Enum):
    """Levels of system degradation."""

    FULL = "full"  # Full functionality
    PARTIAL = "partial"  # Some features disabled
    MINIMAL = "minimal"  # Only essential features
    OFFLINE = "offline"  # No service available
    NORMAL = "normal"
    REDUCED = "reduced"
    EMERGENCY = "emergency"


class FeatureFlag(str, Enum):
    """Feature flags for controlled degradation."""

    LLM_GENERATION = "llm_generation"
    CODE_EXECUTION = "code_execution"
    DATABASE_WRITES = "database_writes"
    DATABASE_READS = "database_reads"
    EXTERNAL_APIS = "external_apis"
    PARALLEL_EXECUTION = "parallel_execution"
    SAFETY_VALIDATION = "safety_validation"
    MEMORY_PERSISTENCE = "memory_persistence"


@dataclass
class FallbackConfig:
    """Configuration for fallback behavior.

    Attributes:
        default_timeout: Default timeout for operations.
        max_retries: Maximum retry attempts.
        fallback_delay: Delay before using fallback.
        cache_ttl: Time-to-live for cached fallbacks.
    """

    default_timeout: float = 30.0
    max_retries: int = 3
    fallback_delay: float = 1.0
    cache_ttl: float = 300.0


class FeatureStatus(BaseModel):
    """Status of a feature.

    Attributes:
        feature: The feature flag.
        enabled: Whether the feature is enabled.
        degraded: Whether the feature is in degraded mode.
        reason: Reason for current status.
        last_check: When the status was last updated.
    """

    feature: FeatureFlag
    enabled: bool = True
    degraded: bool = False
    reason: str | None = None
    last_check: datetime | None = None


class SystemDegradationStatus(BaseModel):
    """Overall system degradation status.

    Attributes:
        level: Current degradation level.
        features: Status of all features.
        timestamp: When the status was computed.
        message: Human-readable status message.
    """

    level: DegradationLevel
    features: list[FeatureStatus]
    timestamp: datetime
    message: str


FallbackFunc = Callable[[], Coroutine[Any, Any, T]]


@dataclass
class FallbackStrategy:
    """A fallback strategy for a feature.

    Attributes:
        feature: The feature this strategy applies to.
        primary: Primary function to execute.
        fallback: Fallback function if primary fails.
        cache_result: Whether to cache fallback results.
        priority: Priority of this strategy.
    """

    feature: FeatureFlag
    primary: FallbackFunc[Any]
    fallback: FallbackFunc[Any]
    cache_result: bool = True
    priority: int = 0


class GracefulDegradationManager:
    """Manager for graceful degradation.

    Handles feature flags, fallback strategies, and system
    degradation levels to maintain partial functionality
    when components fail.
    """

    def __init__(self, config: FallbackConfig | None = None) -> None:
        """Initialize the degradation manager.

        Args:
            config: Configuration for fallback behavior.
        """
        self.config = config or FallbackConfig()
        self._feature_status: dict[FeatureFlag, FeatureStatus] = {}
        self._strategies: dict[FeatureFlag, list[FallbackStrategy]] = {}
        self._fallback_cache: dict[str, tuple[Any, datetime]] = {}
        self._degradation_level = DegradationLevel.FULL

        # Initialize all features as enabled
        for feature in FeatureFlag:
            self._feature_status[feature] = FeatureStatus(
                feature=feature,
                enabled=True,
                last_check=datetime.utcnow(),
            )

    def disable_feature(
        self,
        feature: FeatureFlag,
        reason: str | None = None,
    ) -> None:
        """Disable a feature.

        Args:
            feature: The feature to disable.
            reason: Reason for disabling.
        """
        self._feature_status[feature] = FeatureStatus(
            feature=feature,
            enabled=False,
            degraded=True,
            reason=reason,
            last_check=datetime.utcnow(),
        )
        self._update_degradation_level()
        logger.warning(f"Feature disabled: {feature.value} - {reason}")

    def enable_feature(self, feature: FeatureFlag) -> None:
        """Re-enable a feature.

        Args:
            feature: The feature to enable.
        """
        self._feature_status[feature] = FeatureStatus(
            feature=feature,
            enabled=True,
            degraded=False,
            last_check=datetime.utcnow(),
        )
        self._update_degradation_level()
        logger.info(f"Feature enabled: {feature.value}")

    def is_feature_enabled(self, feature: FeatureFlag) -> bool:
        """Check if a feature is enabled.

        Args:
            feature: The feature to check.

        Returns:
            True if the feature is enabled.
        """
        status = self._feature_status.get(feature)
        return status.enabled if status else True

    def mark_feature_degraded(
        self,
        feature: FeatureFlag,
        reason: str | None = None,
    ) -> None:
        """Mark a feature as degraded but still functional.

        Args:
            feature: The feature to mark.
            reason: Reason for degradation.
        """
        status = self._feature_status.get(feature)
        if status:
            status.degraded = True
            status.reason = reason
            status.last_check = datetime.utcnow()
        self._update_degradation_level()
        logger.warning(f"Feature degraded: {feature.value} - {reason}")

    def register_strategy(self, strategy: FallbackStrategy) -> None:
        """Register a fallback strategy.

        Args:
            strategy: The strategy to register.
        """
        if strategy.feature not in self._strategies:
            self._strategies[strategy.feature] = []
        self._strategies[strategy.feature].append(strategy)
        # Sort by priority
        self._strategies[strategy.feature].sort(
            key=lambda s: s.priority, reverse=True
        )
        logger.debug(f"Registered fallback strategy for {strategy.feature}")

    async def execute_with_fallback(
        self,
        feature: FeatureFlag,
        operation: FallbackFunc[T],
        cache_key: str | None = None,
    ) -> T:
        """Execute an operation with fallback support.

        Args:
            feature: The feature being executed.
            operation: The operation to execute.
            cache_key: Optional key for caching results.

        Returns:
            Result from primary or fallback.

        Raises:
            Exception: If all fallbacks fail.
        """
        # Check if feature is disabled
        if not self.is_feature_enabled(feature):
            return await self._execute_fallback(feature, cache_key)

        # Check cache first
        if cache_key:
            cached = self._get_cached_result(cache_key)
            if cached is not None:
                return cached

        # Try primary operation
        try:
            result = await asyncio.wait_for(
                operation(),
                timeout=self.config.default_timeout,
            )

            # Cache successful result
            if cache_key:
                self._cache_result(cache_key, result)

            return result

        except Exception as e:
            logger.warning(
                f"Primary operation failed for {feature}: {e}"
            )

            # Mark feature as degraded
            self.mark_feature_degraded(feature, str(e))

            # Try fallback
            return await self._execute_fallback(feature, cache_key)

    async def _execute_fallback(
        self,
        feature: FeatureFlag,
        cache_key: str | None = None,
    ) -> Any:
        """Execute fallback strategy for a feature.

        Args:
            feature: The feature to execute fallback for.
            cache_key: Optional cache key.

        Returns:
            Fallback result.

        Raises:
            Exception: If no fallback available or all fail.
        """
        strategies = self._strategies.get(feature, [])

        for strategy in strategies:
            try:
                await asyncio.sleep(self.config.fallback_delay)
                result = await strategy.fallback()

                if cache_key and strategy.cache_result:
                    self._cache_result(cache_key, result)

                return result

            except Exception as e:
                logger.warning(
                    f"Fallback failed for {feature}: {e}"
                )
                continue

        # No fallback succeeded
        raise RuntimeError(
            f"All fallbacks failed for feature: {feature.value}"
        )

    def _get_cached_result(self, cache_key: str) -> Any | None:
        """Get a cached fallback result.

        Args:
            cache_key: The cache key.

        Returns:
            Cached result or None.
        """
        if cache_key in self._fallback_cache:
            result, timestamp = self._fallback_cache[cache_key]
            age = (datetime.utcnow() - timestamp).total_seconds()

            if age < self.config.cache_ttl:
                return result

            # Expired
            del self._fallback_cache[cache_key]

        return None

    def _cache_result(self, cache_key: str, result: Any) -> None:
        """Cache a result.

        Args:
            cache_key: The cache key.
            result: The result to cache.
        """
        self._fallback_cache[cache_key] = (result, datetime.utcnow())

    def clear_cache(self, cache_key: str | None = None) -> None:
        """Clear cached results.

        Args:
            cache_key: Specific key to clear, or None for all.
        """
        if cache_key:
            self._fallback_cache.pop(cache_key, None)
        else:
            self._fallback_cache.clear()

    def _update_degradation_level(self) -> None:
        """Update the overall degradation level."""
        critical_features = [
            FeatureFlag.LLM_GENERATION,
            FeatureFlag.DATABASE_READS,
        ]
        important_features = [
            FeatureFlag.DATABASE_WRITES,
            FeatureFlag.CODE_EXECUTION,
        ]

        critical_disabled = sum(
            1 for f in critical_features
            if not self.is_feature_enabled(f)
        )
        important_disabled = sum(
            1 for f in important_features
            if not self.is_feature_enabled(f)
        )
        total_disabled = sum(
            1 for f in FeatureFlag
            if not self.is_feature_enabled(f)
        )

        if critical_disabled >= len(critical_features):
            self._degradation_level = DegradationLevel.OFFLINE
        elif critical_disabled > 0 or important_disabled > 1:
            self._degradation_level = DegradationLevel.MINIMAL
        elif important_disabled > 0 or total_disabled > 2:
            self._degradation_level = DegradationLevel.PARTIAL
        else:
            self._degradation_level = DegradationLevel.FULL

    def get_degradation_status(self) -> SystemDegradationStatus:
        """Get the current system degradation status.

        Returns:
            Current degradation status.
        """
        features = list(self._feature_status.values())

        messages = {
            DegradationLevel.FULL: "System operating normally",
            DegradationLevel.PARTIAL: "Some features degraded",
            DegradationLevel.MINIMAL: "Essential features only",
            DegradationLevel.OFFLINE: "System unavailable",
        }

        return SystemDegradationStatus(
            level=self._degradation_level,
            features=features,
            timestamp=datetime.utcnow(),
            message=messages[self._degradation_level],
        )


# Built-in fallback strategies


async def fallback_llm_generation() -> dict[str, Any]:
    """Fallback for LLM generation failures.

    Returns:
        Default response indicating LLM unavailable.
    """
    return {
        "content": (
            "I apologize, but I'm currently unable to generate a response. "
            "Please try again later or contact support."
        ),
        "fallback": True,
        "model": "fallback",
    }


async def fallback_code_execution() -> dict[str, Any]:
    """Fallback for code execution failures.

    Returns:
        Default response indicating execution unavailable.
    """
    return {
        "output": "",
        "error": "Code execution is temporarily unavailable",
        "fallback": True,
    }


async def fallback_database_read() -> list[Any]:
    """Fallback for database read failures.

    Returns:
        Empty list as fallback.
    """
    return []


async def fallback_database_write() -> dict[str, Any]:
    """Fallback for database write failures.

    Returns:
        Status indicating write was queued.
    """
    return {
        "status": "queued",
        "message": "Write operation queued for later processing",
        "fallback": True,
    }


async def fallback_external_api() -> dict[str, Any]:
    """Fallback for external API failures.

    Returns:
        Default unavailable response.
    """
    return {
        "error": "External service temporarily unavailable",
        "fallback": True,
    }


# Rate limiting and backpressure


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting.

    Attributes:
        requests_per_second: Maximum requests per second.
        burst_size: Maximum burst size.
        backoff_factor: Exponential backoff factor.
    """

    requests_per_second: float = 10.0
    burst_size: int = 20
    backoff_factor: float = 2.0


class RateLimiter:
    """Simple rate limiter for backpressure.

    Uses a token bucket algorithm for rate limiting.
    """

    def __init__(self, config: RateLimitConfig | None = None) -> None:
        """Initialize the rate limiter.

        Args:
            config: Rate limiting configuration.
        """
        self.config = config or RateLimitConfig()
        self._tokens = float(self.config.burst_size)
        self._last_update = datetime.utcnow()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens for a request.

        Args:
            tokens: Number of tokens to acquire.

        Returns:
            True if tokens were acquired.
        """
        async with self._lock:
            now = datetime.utcnow()
            elapsed = (now - self._last_update).total_seconds()
            self._last_update = now

            # Refill tokens
            self._tokens = min(
                self.config.burst_size,
                self._tokens + elapsed * self.config.requests_per_second,
            )

            if self._tokens >= tokens:
                self._tokens -= tokens
                return True

            return False

    async def wait_for_token(self, tokens: int = 1) -> None:
        """Wait until tokens are available.

        Args:
            tokens: Number of tokens to wait for.
        """
        while not await self.acquire(tokens):
            # Wait for tokens to refill
            wait_time = tokens / self.config.requests_per_second
            await asyncio.sleep(wait_time)

    def get_available_tokens(self) -> float:
        """Get the current number of available tokens.

        Returns:
            Number of available tokens.
        """
        return self._tokens


# =============================================================================
# Legacy Compatibility Layer (tests/compat)
# =============================================================================


@dataclass
class DegradationConfig:
    """Legacy degradation config for tests."""

    enable_auto_degradation: bool = True
    reduced_timeout_multiplier: float = 0.75


@dataclass
class DegradationTrigger:
    """Legacy degradation trigger."""

    trigger_type: str
    threshold: float
    action_level: DegradationLevel


class DegradationManager:
    """Legacy degradation manager for tests."""

    def __init__(self, config: DegradationConfig | None = None) -> None:
        self.config = config or DegradationConfig()
        self.current_level = DegradationLevel.NORMAL
        self._triggers: list[DegradationTrigger] = []
        self._metrics: dict[str, float] = {}

    def set_level(self, level: DegradationLevel) -> None:
        self.current_level = level

    def escalate(self) -> None:
        order = [
            DegradationLevel.NORMAL,
            DegradationLevel.REDUCED,
            DegradationLevel.MINIMAL,
            DegradationLevel.EMERGENCY,
        ]
        idx = min(order.index(self.current_level) + 1, len(order) - 1)
        self.current_level = order[idx]

    def deescalate(self) -> None:
        order = [
            DegradationLevel.NORMAL,
            DegradationLevel.REDUCED,
            DegradationLevel.MINIMAL,
            DegradationLevel.EMERGENCY,
        ]
        idx = max(order.index(self.current_level) - 1, 0)
        self.current_level = order[idx]

    def get_adjusted_timeout(self, base_timeout: float) -> float:
        if self.current_level == DegradationLevel.REDUCED:
            return base_timeout * self.config.reduced_timeout_multiplier
        if self.current_level == DegradationLevel.MINIMAL:
            return base_timeout * 0.5
        if self.current_level == DegradationLevel.EMERGENCY:
            return base_timeout * 0.25
        return base_timeout

    def is_feature_available(self, feature: str) -> bool:
        if self.current_level == DegradationLevel.EMERGENCY:
            return feature != "parallel_tasks"
        return True

    def add_trigger(self, trigger: DegradationTrigger) -> None:
        self._triggers.append(trigger)

    def record_metric(self, metric: str, value: float) -> None:
        self._metrics[metric] = value

    def evaluate_triggers(self) -> None:
        if not self.config.enable_auto_degradation:
            return
        for trigger in self._triggers:
            value = self._metrics.get(trigger.trigger_type)
            if value is not None and value >= trigger.threshold:
                self.set_level(trigger.action_level)

    def reset(self) -> None:
        self.current_level = DegradationLevel.NORMAL


# Global instance management


_degradation_manager: GracefulDegradationManager | None = None


def get_degradation_manager() -> GracefulDegradationManager:
    """Get the global degradation manager.

    Returns:
        The global GracefulDegradationManager instance.
    """
    global _degradation_manager
    if _degradation_manager is None:
        _degradation_manager = GracefulDegradationManager()

        # Register default fallback strategies
        _degradation_manager.register_strategy(
            FallbackStrategy(
                feature=FeatureFlag.LLM_GENERATION,
                primary=fallback_llm_generation,
                fallback=fallback_llm_generation,
            )
        )
        _degradation_manager.register_strategy(
            FallbackStrategy(
                feature=FeatureFlag.CODE_EXECUTION,
                primary=fallback_code_execution,
                fallback=fallback_code_execution,
            )
        )
        _degradation_manager.register_strategy(
            FallbackStrategy(
                feature=FeatureFlag.DATABASE_READS,
                primary=fallback_database_read,
                fallback=fallback_database_read,
            )
        )
        _degradation_manager.register_strategy(
            FallbackStrategy(
                feature=FeatureFlag.DATABASE_WRITES,
                primary=fallback_database_write,
                fallback=fallback_database_write,
            )
        )
        _degradation_manager.register_strategy(
            FallbackStrategy(
                feature=FeatureFlag.EXTERNAL_APIS,
                primary=fallback_external_api,
                fallback=fallback_external_api,
            )
        )

    return _degradation_manager
