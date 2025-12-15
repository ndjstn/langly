"""
Base Tool Classes for Langly Tool Framework.

This module provides the abstract base class and protocols for
creating extensible tools that agents can use during workflow execution.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)


# =============================================================================
# Type Variables
# =============================================================================

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


# =============================================================================
# Tool Enums
# =============================================================================


class ToolCategory(str, Enum):
    """Categories of tools available in the system."""

    FILESYSTEM = "filesystem"
    CODE_EXECUTION = "code_execution"
    WEB_API = "web_api"
    DATABASE = "database"
    SEARCH = "search"
    COMMUNICATION = "communication"
    VERSION_CONTROL = "version_control"
    UTILITY = "utility"


class ToolStatus(str, Enum):
    """Status of a tool."""

    AVAILABLE = "available"
    BUSY = "busy"
    DISABLED = "disabled"
    ERROR = "error"


# =============================================================================
# Tool Input/Output Models
# =============================================================================


class ToolInput(BaseModel):
    """Base model for tool inputs."""

    pass


class ToolOutput(BaseModel):
    """Base model for tool outputs."""

    success: bool = Field(
        description="Whether the tool execution was successful"
    )
    result: Any = Field(
        default=None,
        description="The result of the tool execution"
    )
    error: str | None = Field(
        default=None,
        description="Error message if execution failed"
    )
    execution_time_ms: float = Field(
        default=0.0,
        description="Execution time in milliseconds"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the execution"
    )


class ToolInfo(BaseModel):
    """Information about a tool for registration and discovery."""

    name: str = Field(description="Unique name of the tool")
    description: str = Field(description="Human-readable description")
    category: ToolCategory = Field(description="Tool category")
    version: str = Field(default="1.0.0", description="Tool version")
    input_schema: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON schema for tool inputs"
    )
    output_schema: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON schema for tool outputs"
    )
    requires_approval: bool = Field(
        default=False,
        description="Whether tool execution requires human approval"
    )
    is_async: bool = Field(
        default=True,
        description="Whether the tool runs asynchronously"
    )
    timeout_seconds: int = Field(
        default=60,
        description="Default timeout for tool execution"
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Tags for tool discovery"
    )


# =============================================================================
# Base Tool Class
# =============================================================================


class BaseTool(ABC, Generic[InputT, OutputT]):
    """
    Abstract base class for all tools in the Langly platform.

    Tools are callable units of functionality that agents can use
    during workflow execution. Each tool has:
    - A unique name and description
    - Strongly-typed input and output schemas
    - Execution logic (sync or async)
    - Optional validation and safety checks

    Example:
        class ReadFileTool(BaseTool[ReadFileInput, ReadFileOutput]):
            @property
            def name(self) -> str:
                return "read_file"

            async def execute(
                self, input_data: ReadFileInput
            ) -> ReadFileOutput:
                content = Path(input_data.path).read_text()
                return ReadFileOutput(success=True, content=content)
    """

    def __init__(self) -> None:
        """Initialize the tool."""
        self._status = ToolStatus.AVAILABLE
        self._last_execution: datetime | None = None
        self._execution_count = 0
        self._error_count = 0

    # =========================================================================
    # Abstract Properties
    # =========================================================================

    @property
    @abstractmethod
    def name(self) -> str:
        """Get the unique name of the tool."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Get a human-readable description of the tool."""
        pass

    @property
    @abstractmethod
    def category(self) -> ToolCategory:
        """Get the category of the tool."""
        pass

    @property
    @abstractmethod
    def input_model(self) -> type[InputT]:
        """Get the Pydantic model for tool inputs."""
        pass

    @property
    @abstractmethod
    def output_model(self) -> type[OutputT]:
        """Get the Pydantic model for tool outputs."""
        pass

    # =========================================================================
    # Optional Properties (can be overridden)
    # =========================================================================

    @property
    def version(self) -> str:
        """Get the version of the tool."""
        return "1.0.0"

    @property
    def requires_approval(self) -> bool:
        """Check if tool execution requires human approval."""
        return False

    @property
    def timeout_seconds(self) -> int:
        """Get the default timeout for tool execution."""
        return 60

    @property
    def tags(self) -> list[str]:
        """Get tags for tool discovery."""
        return []

    # =========================================================================
    # Tool Info
    # =========================================================================

    def get_info(self) -> ToolInfo:
        """
        Get information about this tool.

        Returns:
            ToolInfo with all metadata about this tool.
        """
        return ToolInfo(
            name=self.name,
            description=self.description,
            category=self.category,
            version=self.version,
            input_schema=self.input_model.model_json_schema(),
            output_schema=self.output_model.model_json_schema(),
            requires_approval=self.requires_approval,
            is_async=True,
            timeout_seconds=self.timeout_seconds,
            tags=self.tags,
        )

    # =========================================================================
    # Status Management
    # =========================================================================

    @property
    def status(self) -> ToolStatus:
        """Get the current status of the tool."""
        return self._status

    @property
    def last_execution(self) -> datetime | None:
        """Get the timestamp of the last execution."""
        return self._last_execution

    @property
    def execution_count(self) -> int:
        """Get the total number of executions."""
        return self._execution_count

    @property
    def error_count(self) -> int:
        """Get the total number of errors."""
        return self._error_count

    def enable(self) -> None:
        """Enable the tool."""
        if self._status == ToolStatus.DISABLED:
            self._status = ToolStatus.AVAILABLE
            logger.info(f"Tool {self.name} enabled")

    def disable(self) -> None:
        """Disable the tool."""
        self._status = ToolStatus.DISABLED
        logger.info(f"Tool {self.name} disabled")

    # =========================================================================
    # Abstract Methods
    # =========================================================================

    @abstractmethod
    async def execute(self, input_data: InputT) -> OutputT:
        """
        Execute the tool with the given input.

        Args:
            input_data: Validated input data for the tool.

        Returns:
            Output from the tool execution.

        Raises:
            ToolExecutionError: If tool execution fails.
        """
        pass

    # =========================================================================
    # Optional Methods (can be overridden)
    # =========================================================================

    async def validate_input(self, input_data: InputT) -> list[str]:
        """
        Perform additional validation on input data.

        Override this method to add custom validation logic
        beyond Pydantic schema validation.

        Args:
            input_data: The input data to validate.

        Returns:
            List of validation error messages (empty if valid).
        """
        return []

    async def pre_execute(self, input_data: InputT) -> None:
        """
        Hook called before tool execution.

        Override this method to add pre-execution logic
        such as logging, setup, or state preparation.

        Args:
            input_data: The input data for execution.
        """
        pass

    async def post_execute(
        self,
        input_data: InputT,
        output_data: OutputT,
    ) -> None:
        """
        Hook called after tool execution.

        Override this method to add post-execution logic
        such as cleanup, logging, or state updates.

        Args:
            input_data: The input data used for execution.
            output_data: The output from execution.
        """
        pass

    # =========================================================================
    # Execution Wrapper
    # =========================================================================

    async def run(self, input_data: InputT | dict[str, Any]) -> ToolOutput:
        """
        Run the tool with input validation and error handling.

        This is the main entry point for tool execution. It handles:
        - Input parsing and validation
        - Pre/post execution hooks
        - Error handling and logging
        - Metrics collection

        Args:
            input_data: Input data as model instance or dict.

        Returns:
            Standardized ToolOutput with results or errors.
        """
        start_time = datetime.utcnow()

        try:
            # Check tool status
            if self._status == ToolStatus.DISABLED:
                return ToolOutput(
                    success=False,
                    error=f"Tool {self.name} is disabled",
                )

            # Parse input if dict
            if isinstance(input_data, dict):
                parsed_input = self.input_model(**input_data)
            else:
                parsed_input = input_data

            # Additional validation
            validation_errors = await self.validate_input(parsed_input)
            if validation_errors:
                return ToolOutput(
                    success=False,
                    error=f"Validation failed: {'; '.join(validation_errors)}",
                )

            # Set status to busy
            self._status = ToolStatus.BUSY

            # Pre-execution hook
            await self.pre_execute(parsed_input)

            # Execute the tool
            result = await self.execute(parsed_input)

            # Post-execution hook
            await self.post_execute(parsed_input, result)

            # Calculate execution time
            end_time = datetime.utcnow()
            execution_time_ms = (
                end_time - start_time
            ).total_seconds() * 1000

            # Update metrics
            self._execution_count += 1
            self._last_execution = end_time
            self._status = ToolStatus.AVAILABLE

            # Return standardized output
            return ToolOutput(
                success=True,
                result=result.model_dump() if hasattr(result, "model_dump")
                else result,
                execution_time_ms=execution_time_ms,
                metadata={
                    "tool_name": self.name,
                    "tool_version": self.version,
                },
            )

        except Exception as e:
            # Calculate execution time
            end_time = datetime.utcnow()
            execution_time_ms = (
                end_time - start_time
            ).total_seconds() * 1000

            # Update error metrics
            self._error_count += 1
            self._status = ToolStatus.ERROR

            logger.error(f"Tool {self.name} execution failed: {e}")

            return ToolOutput(
                success=False,
                error=str(e),
                execution_time_ms=execution_time_ms,
                metadata={
                    "tool_name": self.name,
                    "tool_version": self.version,
                    "exception_type": type(e).__name__,
                },
            )

    # =========================================================================
    # LangChain Tool Compatibility
    # =========================================================================

    def to_langchain_tool(self) -> Any:
        """
        Convert this tool to a LangChain Tool object.

        Returns:
            LangChain-compatible tool wrapper.
        """
        from langchain_core.tools import StructuredTool

        async def _run(**kwargs: Any) -> str:
            """Wrapper function for LangChain."""
            output = await self.run(kwargs)
            if output.success:
                return str(output.result)
            else:
                return f"Error: {output.error}"

        return StructuredTool.from_function(
            func=_run,
            name=self.name,
            description=self.description,
            args_schema=self.input_model,
            coroutine=_run,
        )
