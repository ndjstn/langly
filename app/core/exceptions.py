"""
Custom exceptions for the Langly multi-agent platform.

This module defines all domain-specific exceptions used throughout
the platform for consistent error handling and reporting.
"""


class LanglyError(Exception):
    """Base exception for all Langly platform errors.

    All custom exceptions should inherit from this class to enable
    consistent exception handling across the application.
    """

    def __init__(self, message: str, details: dict | None = None) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error message.
            details: Optional dictionary with additional error context.
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}


# =============================================================================
# Agent Errors
# =============================================================================


class AgentError(LanglyError):
    """Base exception for agent-related errors.

    Raised when an agent encounters an error during processing.
    """

    def __init__(
        self,
        message: str,
        agent_type: str | None = None,
        details: dict | None = None
    ) -> None:
        """Initialize the agent error.

        Args:
            message: Human-readable error message.
            agent_type: The type of agent that raised the error.
            details: Optional dictionary with additional context.
        """
        super().__init__(message, details)
        self.agent_type = agent_type


class AgentNotFoundError(AgentError):
    """Raised when a requested agent cannot be found."""

    pass


class AgentBusyError(AgentError):
    """Raised when an agent is busy and cannot accept new tasks."""

    pass


# =============================================================================
# LLM Errors
# =============================================================================


class LLMError(LanglyError):
    """Base exception for LLM-related errors."""

    pass


class LLMConnectionError(LLMError):
    """Raised when connection to an LLM service fails."""

    def __init__(
        self,
        message: str = "Failed to connect to LLM service",
        service: str | None = None,
        details: dict | None = None
    ) -> None:
        """Initialize the LLM connection error.

        Args:
            message: Human-readable error message.
            service: The LLM service that failed.
            details: Optional dictionary with additional context.
        """
        super().__init__(message, details)
        self.service = service


class EmbeddingError(LLMError):
    """Raised when embedding generation fails."""

    def __init__(
        self,
        message: str = "Embedding generation failed",
        model: str | None = None,
        details: dict | None = None
    ) -> None:
        """Initialize the embedding error.

        Args:
            message: Human-readable error message.
            model: The embedding model that failed.
            details: Optional dictionary with additional context.
        """
        super().__init__(message, details)
        self.model = model


class ModelNotFoundError(LLMError):
    """Raised when a requested model cannot be found."""

    def __init__(
        self,
        message: str = "Model not found",
        model_name: str | None = None,
        details: dict | None = None
    ) -> None:
        """Initialize the model not found error.

        Args:
            message: Human-readable error message.
            model_name: The name of the model that wasn't found.
            details: Optional dictionary with additional context.
        """
        super().__init__(message, details)
        self.model_name = model_name


# =============================================================================
# Connection Errors
# =============================================================================


class OllamaConnectionError(LanglyError):
    """Raised when connection to Ollama server fails.

    This error indicates that the Ollama service is unreachable,
    not responding, or returned an unexpected error.
    """

    def __init__(
        self,
        message: str = "Failed to connect to Ollama server",
        host: str | None = None,
        details: dict | None = None
    ) -> None:
        """Initialize the Ollama connection error.

        Args:
            message: Human-readable error message.
            host: The Ollama host URL that failed.
            details: Optional dictionary with additional context.
        """
        super().__init__(message, details)
        self.host = host


class Neo4jConnectionError(LanglyError):
    """Raised when connection to Neo4j database fails.

    This error indicates that the Neo4j database is unreachable,
    authentication failed, or the connection was unexpectedly closed.
    """

    def __init__(
        self,
        message: str = "Failed to connect to Neo4j database",
        uri: str | None = None,
        details: dict | None = None
    ) -> None:
        """Initialize the Neo4j connection error.

        Args:
            message: Human-readable error message.
            uri: The Neo4j URI that failed.
            details: Optional dictionary with additional context.
        """
        super().__init__(message, details)
        self.uri = uri


class ModelNotAvailableError(LanglyError):
    """Raised when a requested LLM model is not available.

    This can occur when the model hasn't been pulled to Ollama
    or the model name is incorrect.
    """

    def __init__(
        self,
        message: str = "Model not available",
        model_name: str | None = None,
        details: dict | None = None
    ) -> None:
        """Initialize the model not available error.

        Args:
            message: Human-readable error message.
            model_name: The name of the unavailable model.
            details: Optional dictionary with additional context.
        """
        super().__init__(message, details)
        self.model_name = model_name


# =============================================================================
# Workflow Errors
# =============================================================================


class WorkflowError(LanglyError):
    """Base exception for workflow-related errors."""

    def __init__(
        self,
        message: str,
        workflow_id: str | None = None,
        details: dict | None = None
    ) -> None:
        """Initialize the workflow error.

        Args:
            message: Human-readable error message.
            workflow_id: The ID of the workflow that errored.
            details: Optional dictionary with additional context.
        """
        super().__init__(message, details)
        self.workflow_id = workflow_id


class WorkflowTimeoutError(WorkflowError):
    """Raised when a workflow exceeds its maximum execution time.

    This indicates that the workflow has been running for longer
    than the configured timeout and should be terminated.
    """

    def __init__(
        self,
        message: str = "Workflow execution timed out",
        workflow_id: str | None = None,
        timeout_seconds: int | None = None,
        details: dict | None = None
    ) -> None:
        """Initialize the workflow timeout error.

        Args:
            message: Human-readable error message.
            workflow_id: The ID of the timed-out workflow.
            timeout_seconds: The timeout limit that was exceeded.
            details: Optional dictionary with additional context.
        """
        super().__init__(message, workflow_id, details)
        self.timeout_seconds = timeout_seconds


class LoopDetectedError(WorkflowError):
    """Raised when an infinite loop is detected in the workflow.

    This indicates that the workflow has exceeded its maximum
    iteration count or is repeating the same states without progress.
    """

    def __init__(
        self,
        message: str = "Infinite loop detected in workflow",
        workflow_id: str | None = None,
        iteration_count: int | None = None,
        details: dict | None = None
    ) -> None:
        """Initialize the loop detected error.

        Args:
            message: Human-readable error message.
            workflow_id: The ID of the looping workflow.
            iteration_count: Number of iterations before detection.
            details: Optional dictionary with additional context.
        """
        super().__init__(message, workflow_id, details)
        self.iteration_count = iteration_count


class WorkflowNotFoundError(WorkflowError):
    """Raised when a requested workflow cannot be found."""

    pass


class WorkflowStateError(WorkflowError):
    """Raised when a workflow is in an invalid state for an operation."""

    pass


# =============================================================================
# Human-in-the-Loop Errors
# =============================================================================


class HumanInterventionRequired(LanglyError):
    """Raised when a workflow requires human intervention to continue.

    This is not necessarily an error condition, but rather a signal
    that the workflow needs human input before it can proceed.
    """

    def __init__(
        self,
        message: str = "Human intervention required",
        prompt: str | None = None,
        options: list[str] | None = None,
        workflow_id: str | None = None,
        details: dict | None = None
    ) -> None:
        """Initialize the human intervention required signal.

        Args:
            message: Human-readable message about what's needed.
            prompt: The specific question or request for the human.
            options: Available options for the human to choose from.
            workflow_id: The ID of the workflow requesting intervention.
            details: Optional dictionary with additional context.
        """
        super().__init__(message, details)
        self.prompt = prompt
        self.options = options or []
        self.workflow_id = workflow_id


class InterventionTimeoutError(LanglyError):
    """Raised when a human intervention request times out."""

    def __init__(
        self,
        message: str = "Human intervention request timed out",
        request_id: str | None = None,
        timeout_seconds: int | None = None,
        details: dict | None = None
    ) -> None:
        """Initialize the intervention timeout error.

        Args:
            message: Human-readable error message.
            request_id: The ID of the intervention request.
            timeout_seconds: The timeout limit that was exceeded.
            details: Optional dictionary with additional context.
        """
        super().__init__(message, details)
        self.request_id = request_id
        self.timeout_seconds = timeout_seconds


# =============================================================================
# Tool Errors
# =============================================================================


class ToolError(LanglyError):
    """Base exception for tool-related errors."""

    def __init__(
        self,
        message: str,
        tool_name: str | None = None,
        details: dict | None = None
    ) -> None:
        """Initialize the tool error.

        Args:
            message: Human-readable error message.
            tool_name: The name of the tool that errored.
            details: Optional dictionary with additional context.
        """
        super().__init__(message, details)
        self.tool_name = tool_name


class ToolNotFoundError(ToolError):
    """Raised when a requested tool cannot be found."""

    pass


class ToolExecutionError(ToolError):
    """Raised when a tool fails during execution."""

    pass


class ToolValidationError(ToolError):
    """Raised when tool input validation fails."""

    pass


# =============================================================================
# Safety Errors
# =============================================================================


class SafetyError(LanglyError):
    """Raised when content fails safety validation.

    This indicates that the Granite Guardian or other safety
    mechanisms have flagged content as potentially unsafe.
    """

    def __init__(
        self,
        message: str = "Content failed safety validation",
        content_type: str | None = None,
        reasons: list[str] | None = None,
        details: dict | None = None
    ) -> None:
        """Initialize the safety error.

        Args:
            message: Human-readable error message.
            content_type: The type of content that failed validation.
            reasons: List of reasons why the content was flagged.
            details: Optional dictionary with additional context.
        """
        super().__init__(message, details)
        self.content_type = content_type
        self.reasons = reasons or []


# =============================================================================
# Memory Errors
# =============================================================================


class LanglyMemoryError(LanglyError):
    """Base exception for memory-related errors.

    Named LanglyMemoryError to avoid shadowing Python's built-in MemoryError.
    """

    pass


class MemoryStoreError(LanglyMemoryError):
    """Raised when storing data to memory fails."""

    pass


class MemoryRetrievalError(LanglyMemoryError):
    """Raised when retrieving data from memory fails."""

    pass


# =============================================================================
# Configuration Errors
# =============================================================================


class ConfigurationError(LanglyError):
    """Raised when there is a configuration error."""

    def __init__(
        self,
        message: str = "Configuration error",
        config_key: str | None = None,
        details: dict | None = None
    ) -> None:
        """Initialize the configuration error.

        Args:
            message: Human-readable error message.
            config_key: The configuration key that caused the error.
            details: Optional dictionary with additional context.
        """
        super().__init__(message, details)
        self.config_key = config_key


# =============================================================================
# Reliability Errors
# =============================================================================


class CircuitBreakerOpenError(LanglyError):
    """Raised when a circuit breaker is open and blocking calls.

    This indicates that the protected service has been failing
    and the circuit breaker is preventing further calls to allow recovery.
    """

    def __init__(
        self,
        message: str = "Circuit breaker is open",
        circuit_name: str | None = None,
        details: dict | None = None
    ) -> None:
        """Initialize the circuit breaker open error.

        Args:
            message: Human-readable error message.
            circuit_name: The name of the circuit breaker that is open.
            details: Optional dictionary with additional context.
        """
        super().__init__(message, details)
        self.circuit_name = circuit_name


class RetryExhaustedError(LanglyError):
    """Raised when all retry attempts have been exhausted."""

    def __init__(
        self,
        message: str = "All retry attempts exhausted",
        attempts: int | None = None,
        last_error: Exception | None = None,
        details: dict | None = None
    ) -> None:
        """Initialize the retry exhausted error.

        Args:
            message: Human-readable error message.
            attempts: Number of attempts that were made.
            last_error: The last error that occurred.
            details: Optional dictionary with additional context.
        """
        super().__init__(message, details)
        self.attempts = attempts
        self.last_error = last_error
