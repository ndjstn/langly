"""
Tool Registry for Dynamic Tool Registration and Discovery.

This module provides a centralized registry for managing tools
that agents can use during workflow execution.
"""
from __future__ import annotations

import logging
from typing import Any, TypeVar

from app.tools.base import (
    BaseTool,
    ToolCategory,
    ToolInfo,
    ToolOutput,
    ToolStatus,
)


logger = logging.getLogger(__name__)

# Type variable for tool instances
ToolT = TypeVar("ToolT", bound=BaseTool[Any, Any])


class ToolRegistry:
    """
    Central registry for tool management.

    The registry provides:
    - Dynamic tool registration and deregistration
    - Tool discovery by name, category, or tags
    - Tool execution with validation
    - Health checks for registered tools

    Example:
        registry = ToolRegistry()
        registry.register(ReadFileTool())
        registry.register(WriteFileTool())

        # Execute a tool
        result = await registry.execute("read_file", {"path": "test.txt"})

        # Find tools by category
        fs_tools = registry.get_by_category(ToolCategory.FILESYSTEM)
    """

    def __init__(self) -> None:
        """Initialize the tool registry."""
        self._tools: dict[str, BaseTool[Any, Any]] = {}
        self._categories: dict[ToolCategory, set[str]] = {
            cat: set() for cat in ToolCategory
        }
        self._tags: dict[str, set[str]] = {}

    # =========================================================================
    # Registration
    # =========================================================================

    def register(
        self,
        tool: BaseTool[Any, Any],
        override: bool = False,
    ) -> None:
        """
        Register a tool with the registry.

        Args:
            tool: The tool instance to register.
            override: If True, replace existing tool with same name.

        Raises:
            ValueError: If tool name already exists and override is False.
        """
        name = tool.name

        if name in self._tools and not override:
            raise ValueError(
                f"Tool '{name}' already registered. "
                "Use override=True to replace."
            )

        # Register the tool
        self._tools[name] = tool

        # Index by category
        self._categories[tool.category].add(name)

        # Index by tags
        for tag in tool.tags:
            if tag not in self._tags:
                self._tags[tag] = set()
            self._tags[tag].add(name)

        logger.info(
            f"Registered tool '{name}' "
            f"(category: {tool.category.value}, "
            f"tags: {tool.tags})"
        )

    def register_many(
        self,
        tools: list[BaseTool[Any, Any]],
        override: bool = False,
    ) -> None:
        """
        Register multiple tools at once.

        Args:
            tools: List of tool instances to register.
            override: If True, replace existing tools with same name.
        """
        for tool in tools:
            self.register(tool, override=override)

    def unregister(self, name: str) -> bool:
        """
        Unregister a tool from the registry.

        Args:
            name: The name of the tool to unregister.

        Returns:
            True if tool was removed, False if not found.
        """
        if name not in self._tools:
            logger.warning(f"Tool '{name}' not found in registry")
            return False

        tool = self._tools[name]

        # Remove from category index
        self._categories[tool.category].discard(name)

        # Remove from tag indexes
        for tag in tool.tags:
            if tag in self._tags:
                self._tags[tag].discard(name)
                if not self._tags[tag]:
                    del self._tags[tag]

        # Remove the tool
        del self._tools[name]

        logger.info(f"Unregistered tool '{name}'")
        return True

    # =========================================================================
    # Discovery
    # =========================================================================

    def get(self, name: str) -> BaseTool[Any, Any] | None:
        """
        Get a tool by name.

        Args:
            name: The name of the tool.

        Returns:
            The tool instance or None if not found.
        """
        return self._tools.get(name)

    def get_info(self, name: str) -> ToolInfo | None:
        """
        Get tool information by name.

        Args:
            name: The name of the tool.

        Returns:
            ToolInfo or None if not found.
        """
        tool = self._tools.get(name)
        return tool.get_info() if tool else None

    def get_by_category(
        self,
        category: ToolCategory,
    ) -> list[BaseTool[Any, Any]]:
        """
        Get all tools in a category.

        Args:
            category: The category to search.

        Returns:
            List of tools in the category.
        """
        names = self._categories.get(category, set())
        return [self._tools[name] for name in names if name in self._tools]

    def get_by_tag(self, tag: str) -> list[BaseTool[Any, Any]]:
        """
        Get all tools with a specific tag.

        Args:
            tag: The tag to search.

        Returns:
            List of tools with the tag.
        """
        names = self._tags.get(tag, set())
        return [self._tools[name] for name in names if name in self._tools]

    def search(
        self,
        query: str,
        categories: list[ToolCategory] | None = None,
        tags: list[str] | None = None,
        status: ToolStatus | None = None,
    ) -> list[BaseTool[Any, Any]]:
        """
        Search tools by query with optional filters.

        Args:
            query: Search query (matches name or description).
            categories: Filter by categories (if provided).
            tags: Filter by tags (if provided).
            status: Filter by status (if provided).

        Returns:
            List of matching tools.
        """
        results = []
        query_lower = query.lower()

        for tool in self._tools.values():
            # Check query match
            if (
                query_lower not in tool.name.lower()
                and query_lower not in tool.description.lower()
            ):
                continue

            # Check category filter
            if categories and tool.category not in categories:
                continue

            # Check tag filter
            if tags and not any(t in tool.tags for t in tags):
                continue

            # Check status filter
            if status and tool.status != status:
                continue

            results.append(tool)

        return results

    def list_all(self) -> list[ToolInfo]:
        """
        List information about all registered tools.

        Returns:
            List of ToolInfo for all tools.
        """
        return [tool.get_info() for tool in self._tools.values()]

    def list_names(self) -> list[str]:
        """
        List all registered tool names.

        Returns:
            List of tool names.
        """
        return list(self._tools.keys())

    def list_categories(self) -> dict[ToolCategory, int]:
        """
        List categories and their tool counts.

        Returns:
            Dict mapping categories to tool counts.
        """
        return {
            cat: len(names)
            for cat, names in self._categories.items()
            if names
        }

    def list_tags(self) -> dict[str, int]:
        """
        List tags and their tool counts.

        Returns:
            Dict mapping tags to tool counts.
        """
        return {tag: len(names) for tag, names in self._tags.items()}

    # =========================================================================
    # Execution
    # =========================================================================

    async def execute(
        self,
        name: str,
        input_data: dict[str, Any],
    ) -> ToolOutput:
        """
        Execute a tool by name.

        Args:
            name: The name of the tool to execute.
            input_data: Input data for the tool.

        Returns:
            ToolOutput with results or error.
        """
        tool = self._tools.get(name)

        if not tool:
            return ToolOutput(
                success=False,
                error=f"Tool '{name}' not found in registry",
            )

        return await tool.run(input_data)

    async def execute_many(
        self,
        executions: list[tuple[str, dict[str, Any]]],
    ) -> list[ToolOutput]:
        """
        Execute multiple tools in sequence.

        Args:
            executions: List of (tool_name, input_data) tuples.

        Returns:
            List of ToolOutput results.
        """
        results = []
        for name, input_data in executions:
            result = await self.execute(name, input_data)
            results.append(result)
        return results

    # =========================================================================
    # Status Management
    # =========================================================================

    def enable_tool(self, name: str) -> bool:
        """
        Enable a tool.

        Args:
            name: The name of the tool.

        Returns:
            True if enabled, False if not found.
        """
        tool = self._tools.get(name)
        if tool:
            tool.enable()
            return True
        return False

    def disable_tool(self, name: str) -> bool:
        """
        Disable a tool.

        Args:
            name: The name of the tool.

        Returns:
            True if disabled, False if not found.
        """
        tool = self._tools.get(name)
        if tool:
            tool.disable()
            return True
        return False

    def get_status(self, name: str) -> ToolStatus | None:
        """
        Get the status of a tool.

        Args:
            name: The name of the tool.

        Returns:
            Tool status or None if not found.
        """
        tool = self._tools.get(name)
        return tool.status if tool else None

    def get_all_statuses(self) -> dict[str, ToolStatus]:
        """
        Get statuses of all tools.

        Returns:
            Dict mapping tool names to statuses.
        """
        return {name: tool.status for name, tool in self._tools.items()}

    # =========================================================================
    # LangChain Integration
    # =========================================================================

    def get_langchain_tools(
        self,
        names: list[str] | None = None,
        categories: list[ToolCategory] | None = None,
    ) -> list[Any]:
        """
        Get LangChain-compatible tool objects.

        Args:
            names: Filter by tool names (if provided).
            categories: Filter by categories (if provided).

        Returns:
            List of LangChain tool objects.
        """
        tools = []

        for tool in self._tools.values():
            # Filter by name
            if names and tool.name not in names:
                continue

            # Filter by category
            if categories and tool.category not in categories:
                continue

            # Skip disabled tools
            if tool.status == ToolStatus.DISABLED:
                continue

            tools.append(tool.to_langchain_tool())

        return tools

    # =========================================================================
    # Metrics
    # =========================================================================

    def get_metrics(self) -> dict[str, Any]:
        """
        Get metrics for all registered tools.

        Returns:
            Dict with tool metrics.
        """
        return {
            "total_tools": len(self._tools),
            "by_category": self.list_categories(),
            "by_tag": self.list_tags(),
            "tools": {
                name: {
                    "status": tool.status.value,
                    "execution_count": tool.execution_count,
                    "error_count": tool.error_count,
                    "last_execution": (
                        tool.last_execution.isoformat()
                        if tool.last_execution else None
                    ),
                }
                for name, tool in self._tools.items()
            },
        }

    # =========================================================================
    # Magic Methods
    # =========================================================================

    def __len__(self) -> int:
        """Return the number of registered tools."""
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    def __iter__(self):
        """Iterate over registered tools."""
        return iter(self._tools.values())


# =============================================================================
# Global Registry Instance
# =============================================================================

_global_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """
    Get the global tool registry instance.

    Returns:
        The singleton ToolRegistry instance.
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry


def reset_tool_registry() -> None:
    """Reset the global tool registry (mainly for testing)."""
    global _global_registry
    _global_registry = None
