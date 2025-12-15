"""
External API Tools for Langly Platform.

This module provides tools for making HTTP requests to external APIs,
enabling agents to integrate with external services.
"""
from __future__ import annotations

import asyncio
import logging
from enum import Enum
from typing import Any
from urllib.parse import urljoin

import httpx
from pydantic import BaseModel, Field, field_validator

from app.tools.base import BaseTool, ToolCategory


logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


class HttpMethod(str, Enum):
    """HTTP methods."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


# Default configuration
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_MAX_REDIRECTS = 5
DEFAULT_MAX_RESPONSE_SIZE = 10_000_000  # 10MB


# Blocked hostnames (security)
BLOCKED_HOSTNAMES = [
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "metadata.google.internal",
    "169.254.169.254",  # AWS metadata
    "metadata.azure.com",
]


# =============================================================================
# Input/Output Models
# =============================================================================


class HttpRequestInput(BaseModel):
    """Input for HTTP request tool."""

    url: str = Field(description="URL to request")
    method: HttpMethod = Field(
        default=HttpMethod.GET,
        description="HTTP method"
    )
    headers: dict[str, str] = Field(
        default_factory=dict,
        description="HTTP headers"
    )
    params: dict[str, str] = Field(
        default_factory=dict,
        description="Query parameters"
    )
    body: str | dict[str, Any] | None = Field(
        default=None,
        description="Request body (string or JSON object)"
    )
    timeout_seconds: int = Field(
        default=DEFAULT_TIMEOUT_SECONDS,
        description="Request timeout in seconds",
        ge=1,
        le=120,
    )
    follow_redirects: bool = Field(
        default=True,
        description="Follow HTTP redirects"
    )
    verify_ssl: bool = Field(
        default=True,
        description="Verify SSL certificates"
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL format and security."""
        if not v or not v.strip():
            raise ValueError("URL cannot be empty")

        v = v.strip()

        # Check protocol
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")

        # Check for blocked hostnames
        from urllib.parse import urlparse
        parsed = urlparse(v)
        hostname = parsed.hostname or ""

        if hostname.lower() in BLOCKED_HOSTNAMES:
            raise ValueError(f"Blocked hostname: {hostname}")

        # Check for internal IPs
        if hostname.startswith(("10.", "192.168.", "172.")):
            raise ValueError("Internal IP addresses are blocked")

        return v


class HttpResponseOutput(BaseModel):
    """Output from HTTP request."""

    status_code: int = Field(description="HTTP status code")
    headers: dict[str, str] = Field(description="Response headers")
    body: str = Field(description="Response body")
    content_type: str | None = Field(
        default=None,
        description="Content-Type header"
    )
    response_time_ms: float = Field(description="Response time in ms")
    redirected: bool = Field(description="Whether request was redirected")
    final_url: str = Field(description="Final URL after redirects")
    truncated: bool = Field(
        default=False,
        description="Whether body was truncated"
    )


class WebhookInput(BaseModel):
    """Input for webhook trigger tool."""

    url: str = Field(description="Webhook URL")
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Webhook payload"
    )
    headers: dict[str, str] = Field(
        default_factory=dict,
        description="Additional headers"
    )
    secret: str | None = Field(
        default=None,
        description="Webhook secret for signing"
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL format."""
        if not v or not v.strip():
            raise ValueError("URL cannot be empty")

        v = v.strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")

        return v


class WebhookOutput(BaseModel):
    """Output from webhook trigger."""

    success: bool = Field(description="Whether webhook was sent successfully")
    status_code: int = Field(description="HTTP status code")
    response_body: str | None = Field(
        default=None,
        description="Response body if any"
    )
    request_id: str | None = Field(
        default=None,
        description="Request ID for tracking"
    )


class GraphQLInput(BaseModel):
    """Input for GraphQL request tool."""

    url: str = Field(description="GraphQL endpoint URL")
    query: str = Field(description="GraphQL query or mutation")
    variables: dict[str, Any] = Field(
        default_factory=dict,
        description="Query variables"
    )
    operation_name: str | None = Field(
        default=None,
        description="Operation name if multiple"
    )
    headers: dict[str, str] = Field(
        default_factory=dict,
        description="HTTP headers"
    )
    timeout_seconds: int = Field(
        default=DEFAULT_TIMEOUT_SECONDS,
        description="Request timeout"
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL format."""
        if not v or not v.strip():
            raise ValueError("URL cannot be empty")
        return v.strip()

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Validate query is not empty."""
        if not v or not v.strip():
            raise ValueError("Query cannot be empty")
        return v.strip()


class GraphQLOutput(BaseModel):
    """Output from GraphQL request."""

    data: dict[str, Any] | None = Field(
        default=None,
        description="Query result data"
    )
    errors: list[dict[str, Any]] = Field(
        default_factory=list,
        description="GraphQL errors"
    )
    extensions: dict[str, Any] = Field(
        default_factory=dict,
        description="GraphQL extensions"
    )
    status_code: int = Field(description="HTTP status code")


# =============================================================================
# HTTP Client Wrapper
# =============================================================================


class AsyncHttpClient:
    """
    Async HTTP client with security features.

    Provides:
    - Request timeouts
    - Response size limits
    - Redirect handling
    - SSL verification
    """

    def __init__(
        self,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        max_redirects: int = DEFAULT_MAX_REDIRECTS,
        max_response_size: int = DEFAULT_MAX_RESPONSE_SIZE,
    ) -> None:
        """
        Initialize the HTTP client.

        Args:
            timeout_seconds: Default request timeout.
            max_redirects: Maximum number of redirects.
            max_response_size: Maximum response size in bytes.
        """
        self._timeout = timeout_seconds
        self._max_redirects = max_redirects
        self._max_response_size = max_response_size

    async def request(
        self,
        method: HttpMethod,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        body: str | dict[str, Any] | None = None,
        timeout_seconds: int | None = None,
        follow_redirects: bool = True,
        verify_ssl: bool = True,
    ) -> HttpResponseOutput:
        """
        Make an HTTP request.

        Args:
            method: HTTP method.
            url: Request URL.
            headers: HTTP headers.
            params: Query parameters.
            body: Request body.
            timeout_seconds: Request timeout.
            follow_redirects: Follow redirects.
            verify_ssl: Verify SSL certificates.

        Returns:
            HttpResponseOutput with response details.
        """
        import time
        start_time = time.time()

        timeout = httpx.Timeout(timeout_seconds or self._timeout)

        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=follow_redirects,
            max_redirects=self._max_redirects,
            verify=verify_ssl,
        ) as client:
            # Prepare request kwargs
            kwargs: dict[str, Any] = {
                "method": method.value,
                "url": url,
            }

            if headers:
                kwargs["headers"] = headers

            if params:
                kwargs["params"] = params

            if body is not None:
                if isinstance(body, dict):
                    kwargs["json"] = body
                else:
                    kwargs["content"] = body

            # Make request
            response = await client.request(**kwargs)

            # Get response body with size limit
            body_bytes = await response.aread()
            truncated = False
            if len(body_bytes) > self._max_response_size:
                body_bytes = body_bytes[: self._max_response_size]
                truncated = True

            # Decode body
            try:
                body_text = body_bytes.decode("utf-8")
            except UnicodeDecodeError:
                body_text = body_bytes.decode("latin-1")

            # Calculate response time
            response_time = (time.time() - start_time) * 1000

            return HttpResponseOutput(
                status_code=response.status_code,
                headers=dict(response.headers),
                body=body_text,
                content_type=response.headers.get("content-type"),
                response_time_ms=response_time,
                redirected=len(response.history) > 0,
                final_url=str(response.url),
                truncated=truncated,
            )


# =============================================================================
# Tool Implementations
# =============================================================================


class HttpRequestTool(BaseTool[HttpRequestInput, HttpResponseOutput]):
    """
    Tool for making HTTP requests.

    Provides secure HTTP requests with:
    - Timeout handling
    - Response size limits
    - Blocked hostname protection
    - SSL verification options
    """

    def __init__(
        self,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        max_response_size: int = DEFAULT_MAX_RESPONSE_SIZE,
    ) -> None:
        """Initialize the tool."""
        super().__init__()
        self._client = AsyncHttpClient(
            timeout_seconds=timeout_seconds,
            max_response_size=max_response_size,
        )

    @property
    def name(self) -> str:
        """Get the tool name."""
        return "http_request"

    @property
    def description(self) -> str:
        """Get the tool description."""
        return (
            "Make HTTP requests to external APIs. "
            "Supports GET, POST, PUT, PATCH, DELETE methods."
        )

    @property
    def category(self) -> ToolCategory:
        """Get the tool category."""
        return ToolCategory.WEB_API

    @property
    def input_model(self) -> type[HttpRequestInput]:
        """Get the input model."""
        return HttpRequestInput

    @property
    def output_model(self) -> type[HttpResponseOutput]:
        """Get the output model."""
        return HttpResponseOutput

    @property
    def requires_approval(self) -> bool:
        """Check if tool requires human approval."""
        return True

    @property
    def tags(self) -> list[str]:
        """Get tool tags."""
        return ["http", "api", "request", "web"]

    async def execute(
        self,
        input_data: HttpRequestInput,
    ) -> HttpResponseOutput:
        """Execute the HTTP request."""
        return await self._client.request(
            method=input_data.method,
            url=input_data.url,
            headers=input_data.headers or None,
            params=input_data.params or None,
            body=input_data.body,
            timeout_seconds=input_data.timeout_seconds,
            follow_redirects=input_data.follow_redirects,
            verify_ssl=input_data.verify_ssl,
        )


class WebhookTriggerTool(BaseTool[WebhookInput, WebhookOutput]):
    """
    Tool for triggering webhooks.

    Provides:
    - JSON payload support
    - Signature generation (if secret provided)
    - Response capture
    """

    def __init__(self) -> None:
        """Initialize the tool."""
        super().__init__()
        self._client = AsyncHttpClient()

    @property
    def name(self) -> str:
        """Get the tool name."""
        return "trigger_webhook"

    @property
    def description(self) -> str:
        """Get the tool description."""
        return (
            "Trigger a webhook by sending a POST request "
            "with a JSON payload."
        )

    @property
    def category(self) -> ToolCategory:
        """Get the tool category."""
        return ToolCategory.WEB_API

    @property
    def input_model(self) -> type[WebhookInput]:
        """Get the input model."""
        return WebhookInput

    @property
    def output_model(self) -> type[WebhookOutput]:
        """Get the output model."""
        return WebhookOutput

    @property
    def requires_approval(self) -> bool:
        """Check if tool requires human approval."""
        return True

    @property
    def tags(self) -> list[str]:
        """Get tool tags."""
        return ["webhook", "trigger", "notification"]

    async def execute(self, input_data: WebhookInput) -> WebhookOutput:
        """Execute the webhook trigger."""
        import hashlib
        import hmac
        import uuid

        # Generate request ID
        request_id = str(uuid.uuid4())

        # Build headers
        headers = {
            "Content-Type": "application/json",
            "X-Request-ID": request_id,
            **input_data.headers,
        }

        # Add signature if secret provided
        if input_data.secret:
            import json
            payload_bytes = json.dumps(input_data.payload).encode()
            signature = hmac.new(
                input_data.secret.encode(),
                payload_bytes,
                hashlib.sha256,
            ).hexdigest()
            headers["X-Webhook-Signature"] = f"sha256={signature}"

        try:
            response = await self._client.request(
                method=HttpMethod.POST,
                url=input_data.url,
                headers=headers,
                body=input_data.payload,
                timeout_seconds=30,
            )

            return WebhookOutput(
                success=200 <= response.status_code < 300,
                status_code=response.status_code,
                response_body=response.body if response.body else None,
                request_id=request_id,
            )

        except Exception as e:
            logger.error(f"Webhook trigger failed: {e}")
            return WebhookOutput(
                success=False,
                status_code=0,
                response_body=str(e),
                request_id=request_id,
            )


class GraphQLRequestTool(BaseTool[GraphQLInput, GraphQLOutput]):
    """
    Tool for making GraphQL requests.

    Provides:
    - Query and mutation support
    - Variable handling
    - Error extraction
    """

    def __init__(self) -> None:
        """Initialize the tool."""
        super().__init__()
        self._client = AsyncHttpClient()

    @property
    def name(self) -> str:
        """Get the tool name."""
        return "graphql_request"

    @property
    def description(self) -> str:
        """Get the tool description."""
        return (
            "Make GraphQL queries and mutations to a GraphQL endpoint."
        )

    @property
    def category(self) -> ToolCategory:
        """Get the tool category."""
        return ToolCategory.WEB_API

    @property
    def input_model(self) -> type[GraphQLInput]:
        """Get the input model."""
        return GraphQLInput

    @property
    def output_model(self) -> type[GraphQLOutput]:
        """Get the output model."""
        return GraphQLOutput

    @property
    def requires_approval(self) -> bool:
        """Check if tool requires human approval."""
        return True

    @property
    def tags(self) -> list[str]:
        """Get tool tags."""
        return ["graphql", "api", "query"]

    async def execute(self, input_data: GraphQLInput) -> GraphQLOutput:
        """Execute the GraphQL request."""
        import json

        # Build request body
        body: dict[str, Any] = {
            "query": input_data.query,
        }
        if input_data.variables:
            body["variables"] = input_data.variables
        if input_data.operation_name:
            body["operationName"] = input_data.operation_name

        # Build headers
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            **input_data.headers,
        }

        response: HttpResponseOutput | None = None
        try:
            response = await self._client.request(
                method=HttpMethod.POST,
                url=input_data.url,
                headers=headers,
                body=body,
                timeout_seconds=input_data.timeout_seconds,
            )

            # Parse response
            result = json.loads(response.body)

            return GraphQLOutput(
                data=result.get("data"),
                errors=result.get("errors", []),
                extensions=result.get("extensions", {}),
                status_code=response.status_code,
            )

        except json.JSONDecodeError:
            return GraphQLOutput(
                data=None,
                errors=[{"message": "Invalid JSON response"}],
                extensions={},
                status_code=response.status_code if response else 0,
            )
        except Exception as e:
            return GraphQLOutput(
                data=None,
                errors=[{"message": str(e)}],
                extensions={},
                status_code=0,
            )


# =============================================================================
# Factory Functions
# =============================================================================


def get_api_tools() -> list[BaseTool[Any, Any]]:
    """
    Get all API tools.

    Returns:
        List of API tool instances.
    """
    return [
        HttpRequestTool(),
        WebhookTriggerTool(),
        GraphQLRequestTool(),
    ]
