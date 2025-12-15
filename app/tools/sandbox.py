"""
Code Execution Sandbox for Langly Platform.

This module provides a secure sandboxed environment for executing
code snippets. It implements resource limits, timeout handling,
and output capture for safe code execution.
"""
from __future__ import annotations

import asyncio
import logging
import os
import resource
import signal
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.tools.base import BaseTool, ToolCategory


logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


class SandboxLanguage(str, Enum):
    """Supported languages for code execution."""

    PYTHON = "python"
    BASH = "bash"
    JAVASCRIPT = "javascript"


# Default resource limits
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_MAX_MEMORY_MB = 256
DEFAULT_MAX_OUTPUT_BYTES = 1_000_000  # 1MB


# Language configurations
LANGUAGE_CONFIG = {
    SandboxLanguage.PYTHON: {
        "command": [sys.executable, "-u"],
        "extension": ".py",
        "shebang": "#!/usr/bin/env python3",
    },
    SandboxLanguage.BASH: {
        "command": ["/bin/bash"],
        "extension": ".sh",
        "shebang": "#!/bin/bash",
    },
    SandboxLanguage.JAVASCRIPT: {
        "command": ["node"],
        "extension": ".js",
        "shebang": "",
    },
}


# Dangerous patterns to block
DANGEROUS_PATTERNS = [
    # Python dangerous imports/operations
    "import os",
    "from os import",
    "import subprocess",
    "from subprocess import",
    "import shutil",
    "from shutil import",
    "import sys",
    "from sys import",
    "__import__",
    "exec(",
    "eval(",
    "compile(",
    "open(",
    "file(",
    # Shell dangerous commands
    "rm -rf",
    "sudo",
    "chmod",
    "chown",
    "mkfs",
    "dd if=",
    "> /dev/",
    "curl",
    "wget",
    # Network operations
    "socket",
    "urllib",
    "requests",
    "http.client",
]


# =============================================================================
# Input/Output Models
# =============================================================================


class ExecuteCodeInput(BaseModel):
    """Input for code execution."""

    code: str = Field(description="Code to execute")
    language: SandboxLanguage = Field(
        default=SandboxLanguage.PYTHON,
        description="Programming language"
    )
    timeout_seconds: int = Field(
        default=DEFAULT_TIMEOUT_SECONDS,
        description="Maximum execution time in seconds",
        ge=1,
        le=300,
    )
    allow_network: bool = Field(
        default=False,
        description="Allow network access (use with caution)"
    )
    stdin: str | None = Field(
        default=None,
        description="Input to provide via stdin"
    )
    environment: dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables to set"
    )

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        """Validate code is not empty."""
        if not v or not v.strip():
            raise ValueError("Code cannot be empty")
        return v

    @field_validator("timeout_seconds")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        """Validate timeout is reasonable."""
        if v < 1:
            raise ValueError("Timeout must be at least 1 second")
        if v > 300:
            raise ValueError("Timeout cannot exceed 300 seconds")
        return v


class ExecuteCodeOutput(BaseModel):
    """Output from code execution."""

    stdout: str = Field(description="Standard output")
    stderr: str = Field(description="Standard error")
    exit_code: int = Field(description="Exit code")
    execution_time_seconds: float = Field(
        description="Execution time in seconds"
    )
    timed_out: bool = Field(description="Whether execution timed out")
    memory_exceeded: bool = Field(
        description="Whether memory limit was exceeded"
    )
    truncated: bool = Field(description="Whether output was truncated")


class ValidateCodeInput(BaseModel):
    """Input for code validation."""

    code: str = Field(description="Code to validate")
    language: SandboxLanguage = Field(
        default=SandboxLanguage.PYTHON,
        description="Programming language"
    )
    strict_mode: bool = Field(
        default=True,
        description="Enable strict security checks"
    )


class ValidateCodeOutput(BaseModel):
    """Output from code validation."""

    is_valid: bool = Field(description="Whether code passed validation")
    is_safe: bool = Field(description="Whether code passed safety checks")
    errors: list[str] = Field(
        default_factory=list,
        description="Validation errors"
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Validation warnings"
    )
    blocked_patterns: list[str] = Field(
        default_factory=list,
        description="Dangerous patterns found"
    )


# =============================================================================
# Sandbox Manager
# =============================================================================


class SandboxManager:
    """
    Manages sandboxed code execution environments.

    Provides:
    - Resource-limited code execution
    - Timeout handling
    - Output capture and truncation
    - Security checks
    """

    def __init__(
        self,
        workspace_dir: Path | None = None,
        max_memory_mb: int = DEFAULT_MAX_MEMORY_MB,
        max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
    ) -> None:
        """
        Initialize the sandbox manager.

        Args:
            workspace_dir: Directory for temporary files.
            max_memory_mb: Maximum memory in MB.
            max_output_bytes: Maximum output size in bytes.
        """
        self._workspace_dir = workspace_dir or Path(tempfile.gettempdir())
        self._max_memory_mb = max_memory_mb
        self._max_output_bytes = max_output_bytes

    def check_safety(
        self,
        code: str,
        language: SandboxLanguage,
        strict: bool = True,
    ) -> tuple[bool, list[str]]:
        """
        Check code for dangerous patterns.

        Args:
            code: The code to check.
            language: The programming language.
            strict: Enable strict checking.

        Returns:
            Tuple of (is_safe, list of blocked patterns found).
        """
        blocked = []

        for pattern in DANGEROUS_PATTERNS:
            if pattern.lower() in code.lower():
                blocked.append(pattern)

        # Additional Python-specific checks
        if language == SandboxLanguage.PYTHON and strict:
            # Check for attribute access to dangerous modules
            if ".__" in code:
                blocked.append("dunder attribute access")
            if "globals()" in code or "locals()" in code:
                blocked.append("globals/locals access")

        # Additional Bash-specific checks
        if language == SandboxLanguage.BASH and strict:
            if "|" in code and "rm" in code:
                blocked.append("piped rm command")
            if "$((" in code:
                blocked.append("command substitution")

        return len(blocked) == 0, blocked

    def validate_syntax(
        self,
        code: str,
        language: SandboxLanguage,
    ) -> tuple[bool, list[str]]:
        """
        Validate code syntax.

        Args:
            code: The code to validate.
            language: The programming language.

        Returns:
            Tuple of (is_valid, list of syntax errors).
        """
        errors = []

        if language == SandboxLanguage.PYTHON:
            try:
                compile(code, "<string>", "exec")
            except SyntaxError as e:
                errors.append(f"Syntax error at line {e.lineno}: {e.msg}")

        # For other languages, we rely on runtime errors
        return len(errors) == 0, errors

    def _create_script_file(
        self,
        code: str,
        language: SandboxLanguage,
    ) -> Path:
        """
        Create a temporary script file.

        Args:
            code: The code to write.
            language: The programming language.

        Returns:
            Path to the created file.
        """
        config = LANGUAGE_CONFIG[language]
        suffix = config["extension"]
        shebang = config["shebang"]

        # Add shebang if needed
        if shebang and not code.startswith("#!"):
            code = f"{shebang}\n{code}"

        # Create temp file
        file_id = uuid.uuid4().hex[:8]
        file_path = self._workspace_dir / f"sandbox_{file_id}{suffix}"
        file_path.write_text(code)
        file_path.chmod(0o700)

        return file_path

    async def execute(
        self,
        code: str,
        language: SandboxLanguage,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        stdin: str | None = None,
        environment: dict[str, str] | None = None,
    ) -> ExecuteCodeOutput:
        """
        Execute code in a sandboxed environment.

        Args:
            code: The code to execute.
            language: The programming language.
            timeout_seconds: Maximum execution time.
            stdin: Input to provide via stdin.
            environment: Additional environment variables.

        Returns:
            ExecuteCodeOutput with execution results.
        """
        script_path: Path | None = None
        start_time = datetime.utcnow()
        timed_out = False
        memory_exceeded = False
        truncated = False

        try:
            # Create script file
            script_path = self._create_script_file(code, language)

            # Build command
            config = LANGUAGE_CONFIG[language]
            command = config["command"] + [str(script_path)]

            # Build environment
            env = os.environ.copy()
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            env["PYTHONUNBUFFERED"] = "1"
            if environment:
                env.update(environment)

            # Create subprocess
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE if stdin else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=str(self._workspace_dir),
                preexec_fn=self._set_resource_limits,
            )

            # Run with timeout
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(
                        input=stdin.encode() if stdin else None
                    ),
                    timeout=timeout_seconds,
                )
            except asyncio.TimeoutError:
                timed_out = True
                process.kill()
                await process.wait()
                stdout_bytes = b""
                stderr_bytes = b"Execution timed out"

            # Truncate output if needed
            if len(stdout_bytes) > self._max_output_bytes:
                stdout_bytes = stdout_bytes[: self._max_output_bytes]
                truncated = True
            if len(stderr_bytes) > self._max_output_bytes:
                stderr_bytes = stderr_bytes[: self._max_output_bytes]
                truncated = True

            # Decode output
            try:
                stdout = stdout_bytes.decode("utf-8", errors="replace")
            except Exception:
                stdout = str(stdout_bytes)
            try:
                stderr = stderr_bytes.decode("utf-8", errors="replace")
            except Exception:
                stderr = str(stderr_bytes)

            # Check for memory error
            if "MemoryError" in stderr or "Cannot allocate memory" in stderr:
                memory_exceeded = True

            # Calculate execution time
            end_time = datetime.utcnow()
            execution_time = (end_time - start_time).total_seconds()

            return ExecuteCodeOutput(
                stdout=stdout,
                stderr=stderr,
                exit_code=process.returncode or 0,
                execution_time_seconds=execution_time,
                timed_out=timed_out,
                memory_exceeded=memory_exceeded,
                truncated=truncated,
            )

        except Exception as e:
            end_time = datetime.utcnow()
            execution_time = (end_time - start_time).total_seconds()

            return ExecuteCodeOutput(
                stdout="",
                stderr=str(e),
                exit_code=-1,
                execution_time_seconds=execution_time,
                timed_out=timed_out,
                memory_exceeded=memory_exceeded,
                truncated=truncated,
            )

        finally:
            # Cleanup
            if script_path and script_path.exists():
                try:
                    script_path.unlink()
                except Exception:
                    pass

    def _set_resource_limits(self) -> None:
        """Set resource limits for the subprocess."""
        # Set memory limit
        memory_bytes = self._max_memory_mb * 1024 * 1024
        try:
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        except (ValueError, resource.error):
            pass

        # Set CPU time limit (soft and hard)
        try:
            resource.setrlimit(resource.RLIMIT_CPU, (60, 120))
        except (ValueError, resource.error):
            pass

        # Disable core dumps
        try:
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        except (ValueError, resource.error):
            pass

        # Limit number of processes
        try:
            resource.setrlimit(resource.RLIMIT_NPROC, (32, 64))
        except (ValueError, resource.error):
            pass


# =============================================================================
# Tool Implementations
# =============================================================================


class ExecuteCodeTool(BaseTool[ExecuteCodeInput, ExecuteCodeOutput]):
    """
    Tool for executing code in a sandboxed environment.

    Provides secure code execution with:
    - Resource limits (memory, CPU time)
    - Timeout handling
    - Output capture
    - Safety checks
    """

    def __init__(
        self,
        workspace_dir: Path | None = None,
        max_memory_mb: int = DEFAULT_MAX_MEMORY_MB,
    ) -> None:
        """Initialize the tool."""
        super().__init__()
        self._sandbox = SandboxManager(
            workspace_dir=workspace_dir,
            max_memory_mb=max_memory_mb,
        )

    @property
    def name(self) -> str:
        """Get the tool name."""
        return "execute_code"

    @property
    def description(self) -> str:
        """Get the tool description."""
        return (
            "Execute code in a sandboxed environment. "
            "Supports Python, Bash, and JavaScript."
        )

    @property
    def category(self) -> ToolCategory:
        """Get the tool category."""
        return ToolCategory.CODE_EXECUTION

    @property
    def input_model(self) -> type[ExecuteCodeInput]:
        """Get the input model."""
        return ExecuteCodeInput

    @property
    def output_model(self) -> type[ExecuteCodeOutput]:
        """Get the output model."""
        return ExecuteCodeOutput

    @property
    def requires_approval(self) -> bool:
        """Check if tool requires human approval."""
        return True

    @property
    def timeout_seconds(self) -> int:
        """Get the default timeout."""
        return DEFAULT_TIMEOUT_SECONDS * 2  # Extra buffer

    @property
    def tags(self) -> list[str]:
        """Get tool tags."""
        return ["code", "execute", "sandbox", "run"]

    async def validate_input(
        self,
        input_data: ExecuteCodeInput,
    ) -> list[str]:
        """Validate input data with safety checks."""
        errors = []

        # Safety check
        is_safe, blocked = self._sandbox.check_safety(
            input_data.code,
            input_data.language,
        )

        if not is_safe:
            errors.append(
                f"Code contains dangerous patterns: {', '.join(blocked)}"
            )

        # Syntax check for Python
        if input_data.language == SandboxLanguage.PYTHON:
            is_valid, syntax_errors = self._sandbox.validate_syntax(
                input_data.code,
                input_data.language,
            )
            errors.extend(syntax_errors)

        return errors

    async def execute(
        self,
        input_data: ExecuteCodeInput,
    ) -> ExecuteCodeOutput:
        """Execute code in sandbox."""
        return await self._sandbox.execute(
            code=input_data.code,
            language=input_data.language,
            timeout_seconds=input_data.timeout_seconds,
            stdin=input_data.stdin,
            environment=input_data.environment,
        )


class ValidateCodeTool(BaseTool[ValidateCodeInput, ValidateCodeOutput]):
    """
    Tool for validating code without executing it.

    Performs:
    - Syntax validation
    - Safety analysis
    - Pattern detection
    """

    def __init__(self) -> None:
        """Initialize the tool."""
        super().__init__()
        self._sandbox = SandboxManager()

    @property
    def name(self) -> str:
        """Get the tool name."""
        return "validate_code"

    @property
    def description(self) -> str:
        """Get the tool description."""
        return (
            "Validate code for syntax errors and security issues "
            "without executing it."
        )

    @property
    def category(self) -> ToolCategory:
        """Get the tool category."""
        return ToolCategory.CODE_EXECUTION

    @property
    def input_model(self) -> type[ValidateCodeInput]:
        """Get the input model."""
        return ValidateCodeInput

    @property
    def output_model(self) -> type[ValidateCodeOutput]:
        """Get the output model."""
        return ValidateCodeOutput

    @property
    def tags(self) -> list[str]:
        """Get tool tags."""
        return ["code", "validate", "lint", "check"]

    async def execute(
        self,
        input_data: ValidateCodeInput,
    ) -> ValidateCodeOutput:
        """Validate the code."""
        errors = []
        warnings = []
        blocked_patterns = []

        # Syntax validation
        is_valid, syntax_errors = self._sandbox.validate_syntax(
            input_data.code,
            input_data.language,
        )
        errors.extend(syntax_errors)

        # Safety check
        is_safe, blocked = self._sandbox.check_safety(
            input_data.code,
            input_data.language,
            strict=input_data.strict_mode,
        )
        blocked_patterns.extend(blocked)

        # Add warnings for non-blocking issues
        if input_data.language == SandboxLanguage.PYTHON:
            # Check for common issues
            if "print(" in input_data.code and "return" not in input_data.code:
                warnings.append(
                    "Code uses print() but may not return a value"
                )
            if "while True" in input_data.code:
                warnings.append(
                    "Infinite loop detected - ensure there's a break condition"
                )

        return ValidateCodeOutput(
            is_valid=is_valid,
            is_safe=is_safe,
            errors=errors,
            warnings=warnings,
            blocked_patterns=blocked_patterns,
        )


# =============================================================================
# Factory Functions
# =============================================================================


def get_sandbox_tools(
    workspace_dir: Path | None = None,
) -> list[BaseTool[Any, Any]]:
    """
    Get all sandbox tools.

    Args:
        workspace_dir: Directory for temporary files.

    Returns:
        List of sandbox tool instances.
    """
    return [
        ExecuteCodeTool(workspace_dir=workspace_dir),
        ValidateCodeTool(),
    ]
