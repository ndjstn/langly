"""
File System Tools for Langly Platform.

This module provides secure file system operations that agents
can use to read, write, search, and manipulate files within
the project workspace.
"""
from __future__ import annotations

import fnmatch
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.tools.base import BaseTool, ToolCategory


logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

# Default workspace root - can be overridden
DEFAULT_WORKSPACE_ROOT = Path.cwd()

# Patterns to exclude from operations
EXCLUDED_PATTERNS = [
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".env",
    ".env.*",
    "*.key",
    "*.pem",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
]


# =============================================================================
# Input/Output Models
# =============================================================================


class ReadFileInput(BaseModel):
    """Input for reading a file."""

    path: str = Field(description="Path to the file to read")
    encoding: str = Field(
        default="utf-8",
        description="File encoding"
    )
    start_line: int | None = Field(
        default=None,
        description="Starting line number (1-indexed)"
    )
    end_line: int | None = Field(
        default=None,
        description="Ending line number (inclusive)"
    )

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        """Validate path is not empty."""
        if not v or not v.strip():
            raise ValueError("Path cannot be empty")
        return v.strip()


class ReadFileOutput(BaseModel):
    """Output from reading a file."""

    content: str = Field(description="File content")
    path: str = Field(description="Absolute path to the file")
    size_bytes: int = Field(description="File size in bytes")
    line_count: int = Field(description="Total number of lines")
    encoding: str = Field(description="File encoding used")


class WriteFileInput(BaseModel):
    """Input for writing a file."""

    path: str = Field(description="Path to write the file")
    content: str = Field(description="Content to write")
    encoding: str = Field(default="utf-8", description="File encoding")
    create_dirs: bool = Field(
        default=True,
        description="Create parent directories if needed"
    )
    overwrite: bool = Field(
        default=True,
        description="Overwrite existing file"
    )

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        """Validate path is not empty."""
        if not v or not v.strip():
            raise ValueError("Path cannot be empty")
        return v.strip()


class WriteFileOutput(BaseModel):
    """Output from writing a file."""

    path: str = Field(description="Absolute path to the file")
    size_bytes: int = Field(description="Size of written content")
    created: bool = Field(description="Whether file was created (vs updated)")


class ListFilesInput(BaseModel):
    """Input for listing files."""

    path: str = Field(
        default=".",
        description="Directory path to list"
    )
    pattern: str | None = Field(
        default=None,
        description="Glob pattern to filter files"
    )
    recursive: bool = Field(
        default=False,
        description="List files recursively"
    )
    include_hidden: bool = Field(
        default=False,
        description="Include hidden files"
    )
    files_only: bool = Field(
        default=False,
        description="Only list files, not directories"
    )
    dirs_only: bool = Field(
        default=False,
        description="Only list directories, not files"
    )


class FileInfo(BaseModel):
    """Information about a file or directory."""

    path: str = Field(description="Path relative to workspace")
    name: str = Field(description="File or directory name")
    is_file: bool = Field(description="True if file, False if directory")
    size_bytes: int = Field(description="Size in bytes")
    modified_at: datetime = Field(description="Last modification time")


class ListFilesOutput(BaseModel):
    """Output from listing files."""

    entries: list[FileInfo] = Field(description="List of files and dirs")
    total_count: int = Field(description="Total number of entries")
    directory: str = Field(description="Directory that was listed")


class SearchFilesInput(BaseModel):
    """Input for searching file contents."""

    path: str = Field(default=".", description="Directory to search in")
    pattern: str = Field(description="Search pattern (regex or text)")
    is_regex: bool = Field(
        default=False,
        description="Treat pattern as regex"
    )
    case_sensitive: bool = Field(
        default=True,
        description="Case-sensitive search"
    )
    file_pattern: str | None = Field(
        default=None,
        description="Glob pattern to filter files"
    )
    max_results: int = Field(
        default=100,
        description="Maximum number of results"
    )


class SearchMatch(BaseModel):
    """A search match in a file."""

    file: str = Field(description="File path")
    line_number: int = Field(description="Line number (1-indexed)")
    line: str = Field(description="Line content")
    match: str = Field(description="Matched text")


class SearchFilesOutput(BaseModel):
    """Output from searching files."""

    matches: list[SearchMatch] = Field(description="List of matches")
    total_matches: int = Field(description="Total number of matches")
    files_searched: int = Field(description="Number of files searched")


class DeleteFileInput(BaseModel):
    """Input for deleting a file."""

    path: str = Field(description="Path to the file or directory to delete")
    recursive: bool = Field(
        default=False,
        description="For directories, delete recursively"
    )

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        """Validate path is not empty."""
        if not v or not v.strip():
            raise ValueError("Path cannot be empty")
        return v.strip()


class DeleteFileOutput(BaseModel):
    """Output from deleting a file."""

    path: str = Field(description="Path that was deleted")
    was_directory: bool = Field(description="Whether it was a directory")
    items_deleted: int = Field(
        description="Number of items deleted (for dirs)"
    )


# =============================================================================
# Helper Functions
# =============================================================================


def is_path_safe(path: Path, workspace_root: Path) -> bool:
    """
    Check if a path is safe to access.

    Args:
        path: The path to check.
        workspace_root: The workspace root directory.

    Returns:
        True if the path is within the workspace.
    """
    try:
        resolved = path.resolve()
        return resolved.is_relative_to(workspace_root.resolve())
    except (ValueError, RuntimeError):
        return False


def is_excluded(path: Path) -> bool:
    """
    Check if a path matches excluded patterns.

    Args:
        path: The path to check.

    Returns:
        True if the path should be excluded.
    """
    for pattern in EXCLUDED_PATTERNS:
        if fnmatch.fnmatch(path.name, pattern):
            return True
        # Also check parent directories
        for parent in path.parents:
            if fnmatch.fnmatch(parent.name, pattern):
                return True
    return False


def resolve_path(
    path: str,
    workspace_root: Path | None = None,
) -> Path:
    """
    Resolve a path relative to workspace root.

    Args:
        path: The path string to resolve.
        workspace_root: The workspace root (default: cwd).

    Returns:
        Resolved absolute path.

    Raises:
        ValueError: If path is outside workspace.
    """
    if workspace_root is None:
        workspace_root = DEFAULT_WORKSPACE_ROOT

    # Handle absolute paths
    path_obj = Path(path)
    if path_obj.is_absolute():
        resolved = path_obj.resolve()
    else:
        resolved = (workspace_root / path_obj).resolve()

    # Security check
    if not is_path_safe(resolved, workspace_root):
        raise ValueError(
            f"Path '{path}' is outside workspace root"
        )

    return resolved


# =============================================================================
# Tool Implementations
# =============================================================================


class ReadFileTool(BaseTool[ReadFileInput, ReadFileOutput]):
    """
    Tool for reading file contents.

    Provides secure file reading with optional line range selection.
    """

    def __init__(self, workspace_root: Path | None = None) -> None:
        """Initialize the tool."""
        super().__init__()
        self._workspace_root = workspace_root or DEFAULT_WORKSPACE_ROOT

    @property
    def name(self) -> str:
        """Get the tool name."""
        return "read_file"

    @property
    def description(self) -> str:
        """Get the tool description."""
        return (
            "Read the contents of a file. "
            "Optionally specify a line range to read."
        )

    @property
    def category(self) -> ToolCategory:
        """Get the tool category."""
        return ToolCategory.FILESYSTEM

    @property
    def input_model(self) -> type[ReadFileInput]:
        """Get the input model."""
        return ReadFileInput

    @property
    def output_model(self) -> type[ReadFileOutput]:
        """Get the output model."""
        return ReadFileOutput

    @property
    def tags(self) -> list[str]:
        """Get tool tags."""
        return ["file", "read", "content"]

    async def validate_input(self, input_data: ReadFileInput) -> list[str]:
        """Validate input data."""
        errors = []

        # Check line range validity
        if input_data.start_line is not None and input_data.start_line < 1:
            errors.append("start_line must be >= 1")

        if input_data.end_line is not None and input_data.end_line < 1:
            errors.append("end_line must be >= 1")

        if (
            input_data.start_line is not None
            and input_data.end_line is not None
            and input_data.start_line > input_data.end_line
        ):
            errors.append("start_line must be <= end_line")

        return errors

    async def execute(self, input_data: ReadFileInput) -> ReadFileOutput:
        """Execute the file read operation."""
        # Resolve path
        file_path = resolve_path(input_data.path, self._workspace_root)

        # Check if file exists
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {input_data.path}")

        if not file_path.is_file():
            raise ValueError(f"Path is not a file: {input_data.path}")

        # Check excluded patterns
        if is_excluded(file_path):
            raise PermissionError(
                f"Access denied to excluded path: {input_data.path}"
            )

        # Read file content
        content = file_path.read_text(encoding=input_data.encoding)
        lines = content.splitlines(keepends=True)
        total_lines = len(lines)

        # Apply line range if specified
        if input_data.start_line is not None or input_data.end_line is not None:
            start = (input_data.start_line or 1) - 1
            end = input_data.end_line or total_lines
            lines = lines[start:end]
            content = "".join(lines)

        return ReadFileOutput(
            content=content,
            path=str(file_path),
            size_bytes=file_path.stat().st_size,
            line_count=total_lines,
            encoding=input_data.encoding,
        )


class WriteFileTool(BaseTool[WriteFileInput, WriteFileOutput]):
    """
    Tool for writing file contents.

    Provides secure file writing with directory creation.
    """

    def __init__(self, workspace_root: Path | None = None) -> None:
        """Initialize the tool."""
        super().__init__()
        self._workspace_root = workspace_root or DEFAULT_WORKSPACE_ROOT

    @property
    def name(self) -> str:
        """Get the tool name."""
        return "write_file"

    @property
    def description(self) -> str:
        """Get the tool description."""
        return (
            "Write content to a file. "
            "Creates parent directories if needed."
        )

    @property
    def category(self) -> ToolCategory:
        """Get the tool category."""
        return ToolCategory.FILESYSTEM

    @property
    def input_model(self) -> type[WriteFileInput]:
        """Get the input model."""
        return WriteFileInput

    @property
    def output_model(self) -> type[WriteFileOutput]:
        """Get the output model."""
        return WriteFileOutput

    @property
    def requires_approval(self) -> bool:
        """Check if tool requires human approval."""
        return True

    @property
    def tags(self) -> list[str]:
        """Get tool tags."""
        return ["file", "write", "create"]

    async def execute(self, input_data: WriteFileInput) -> WriteFileOutput:
        """Execute the file write operation."""
        # Resolve path
        file_path = resolve_path(input_data.path, self._workspace_root)

        # Check excluded patterns
        if is_excluded(file_path):
            raise PermissionError(
                f"Access denied to excluded path: {input_data.path}"
            )

        # Check if file exists
        file_exists = file_path.exists()
        if file_exists and not input_data.overwrite:
            raise FileExistsError(
                f"File already exists: {input_data.path}"
            )

        # Create parent directories if needed
        if input_data.create_dirs:
            file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write content
        file_path.write_text(input_data.content, encoding=input_data.encoding)

        return WriteFileOutput(
            path=str(file_path),
            size_bytes=len(input_data.content.encode(input_data.encoding)),
            created=not file_exists,
        )


class ListFilesTool(BaseTool[ListFilesInput, ListFilesOutput]):
    """
    Tool for listing files and directories.

    Provides directory listing with filtering options.
    """

    def __init__(self, workspace_root: Path | None = None) -> None:
        """Initialize the tool."""
        super().__init__()
        self._workspace_root = workspace_root or DEFAULT_WORKSPACE_ROOT

    @property
    def name(self) -> str:
        """Get the tool name."""
        return "list_files"

    @property
    def description(self) -> str:
        """Get the tool description."""
        return (
            "List files and directories in a path. "
            "Supports glob patterns and recursive listing."
        )

    @property
    def category(self) -> ToolCategory:
        """Get the tool category."""
        return ToolCategory.FILESYSTEM

    @property
    def input_model(self) -> type[ListFilesInput]:
        """Get the input model."""
        return ListFilesInput

    @property
    def output_model(self) -> type[ListFilesOutput]:
        """Get the output model."""
        return ListFilesOutput

    @property
    def tags(self) -> list[str]:
        """Get tool tags."""
        return ["file", "list", "directory"]

    async def execute(self, input_data: ListFilesInput) -> ListFilesOutput:
        """Execute the list files operation."""
        # Resolve path
        dir_path = resolve_path(input_data.path, self._workspace_root)

        # Check if directory exists
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {input_data.path}")

        if not dir_path.is_dir():
            raise ValueError(f"Path is not a directory: {input_data.path}")

        entries = []

        # Get files/directories
        if input_data.recursive:
            iterator = dir_path.rglob(input_data.pattern or "*")
        else:
            iterator = dir_path.glob(input_data.pattern or "*")

        for entry in iterator:
            # Skip hidden files if not included
            if not input_data.include_hidden and entry.name.startswith("."):
                continue

            # Skip excluded patterns
            if is_excluded(entry):
                continue

            # Apply file/dir filters
            if input_data.files_only and not entry.is_file():
                continue
            if input_data.dirs_only and not entry.is_dir():
                continue

            # Get file info
            try:
                stat = entry.stat()
                entries.append(FileInfo(
                    path=str(entry.relative_to(self._workspace_root)),
                    name=entry.name,
                    is_file=entry.is_file(),
                    size_bytes=stat.st_size if entry.is_file() else 0,
                    modified_at=datetime.fromtimestamp(stat.st_mtime),
                ))
            except (OSError, PermissionError):
                # Skip files we can't access
                continue

        return ListFilesOutput(
            entries=sorted(entries, key=lambda e: (not e.is_file, e.path)),
            total_count=len(entries),
            directory=str(dir_path.relative_to(self._workspace_root)),
        )


class SearchFilesTool(BaseTool[SearchFilesInput, SearchFilesOutput]):
    """
    Tool for searching file contents.

    Provides text and regex search across files.
    """

    def __init__(self, workspace_root: Path | None = None) -> None:
        """Initialize the tool."""
        super().__init__()
        self._workspace_root = workspace_root or DEFAULT_WORKSPACE_ROOT

    @property
    def name(self) -> str:
        """Get the tool name."""
        return "search_files"

    @property
    def description(self) -> str:
        """Get the tool description."""
        return (
            "Search for text or patterns in files. "
            "Supports regex and glob file patterns."
        )

    @property
    def category(self) -> ToolCategory:
        """Get the tool category."""
        return ToolCategory.SEARCH

    @property
    def input_model(self) -> type[SearchFilesInput]:
        """Get the input model."""
        return SearchFilesInput

    @property
    def output_model(self) -> type[SearchFilesOutput]:
        """Get the output model."""
        return SearchFilesOutput

    @property
    def tags(self) -> list[str]:
        """Get tool tags."""
        return ["search", "grep", "find"]

    async def execute(self, input_data: SearchFilesInput) -> SearchFilesOutput:
        """Execute the search operation."""
        # Resolve path
        dir_path = resolve_path(input_data.path, self._workspace_root)

        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {input_data.path}")

        # Build regex pattern
        if input_data.is_regex:
            flags = 0 if input_data.case_sensitive else re.IGNORECASE
            try:
                pattern = re.compile(input_data.pattern, flags)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern: {e}") from e
        else:
            escaped = re.escape(input_data.pattern)
            flags = 0 if input_data.case_sensitive else re.IGNORECASE
            pattern = re.compile(escaped, flags)

        matches = []
        files_searched = 0

        # Search files
        glob_pattern = input_data.file_pattern or "**/*"
        for file_path in dir_path.glob(glob_pattern):
            # Skip non-files
            if not file_path.is_file():
                continue

            # Skip excluded patterns
            if is_excluded(file_path):
                continue

            # Skip binary files (simple heuristic)
            if file_path.suffix in [
                ".exe", ".dll", ".so", ".dylib", ".bin",
                ".jpg", ".png", ".gif", ".ico", ".pdf",
                ".zip", ".tar", ".gz", ".rar",
            ]:
                continue

            files_searched += 1

            try:
                content = file_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue

            # Search content
            for line_num, line in enumerate(content.splitlines(), 1):
                match = pattern.search(line)
                if match:
                    matches.append(SearchMatch(
                        file=str(file_path.relative_to(self._workspace_root)),
                        line_number=line_num,
                        line=line.strip(),
                        match=match.group(),
                    ))

                    if len(matches) >= input_data.max_results:
                        break

            if len(matches) >= input_data.max_results:
                break

        return SearchFilesOutput(
            matches=matches,
            total_matches=len(matches),
            files_searched=files_searched,
        )


class DeleteFileTool(BaseTool[DeleteFileInput, DeleteFileOutput]):
    """
    Tool for deleting files and directories.

    Provides secure file deletion with safety checks.
    """

    def __init__(self, workspace_root: Path | None = None) -> None:
        """Initialize the tool."""
        super().__init__()
        self._workspace_root = workspace_root or DEFAULT_WORKSPACE_ROOT

    @property
    def name(self) -> str:
        """Get the tool name."""
        return "delete_file"

    @property
    def description(self) -> str:
        """Get the tool description."""
        return (
            "Delete a file or directory. "
            "Use recursive=True for non-empty directories."
        )

    @property
    def category(self) -> ToolCategory:
        """Get the tool category."""
        return ToolCategory.FILESYSTEM

    @property
    def input_model(self) -> type[DeleteFileInput]:
        """Get the input model."""
        return DeleteFileInput

    @property
    def output_model(self) -> type[DeleteFileOutput]:
        """Get the output model."""
        return DeleteFileOutput

    @property
    def requires_approval(self) -> bool:
        """Check if tool requires human approval."""
        return True

    @property
    def tags(self) -> list[str]:
        """Get tool tags."""
        return ["file", "delete", "remove"]

    async def execute(self, input_data: DeleteFileInput) -> DeleteFileOutput:
        """Execute the delete operation."""
        # Resolve path
        target_path = resolve_path(input_data.path, self._workspace_root)

        # Check if exists
        if not target_path.exists():
            raise FileNotFoundError(f"Path not found: {input_data.path}")

        # Check excluded patterns
        if is_excluded(target_path):
            raise PermissionError(
                f"Access denied to excluded path: {input_data.path}"
            )

        was_directory = target_path.is_dir()
        items_deleted = 0

        if was_directory:
            if input_data.recursive:
                # Count items
                for _ in target_path.rglob("*"):
                    items_deleted += 1
                # Delete recursively
                import shutil
                shutil.rmtree(target_path)
            else:
                # Try to remove empty directory
                try:
                    target_path.rmdir()
                except OSError as e:
                    raise ValueError(
                        f"Directory is not empty. "
                        f"Use recursive=True to delete: {e}"
                    ) from e
        else:
            os.remove(target_path)
            items_deleted = 1

        return DeleteFileOutput(
            path=str(target_path),
            was_directory=was_directory,
            items_deleted=items_deleted,
        )


# =============================================================================
# Factory Functions
# =============================================================================


def get_filesystem_tools(
    workspace_root: Path | None = None,
) -> list[BaseTool[Any, Any]]:
    """
    Get all filesystem tools.

    Args:
        workspace_root: The workspace root directory.

    Returns:
        List of filesystem tool instances.
    """
    return [
        ReadFileTool(workspace_root),
        WriteFileTool(workspace_root),
        ListFilesTool(workspace_root),
        SearchFilesTool(workspace_root),
        DeleteFileTool(workspace_root),
    ]
