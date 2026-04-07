# =============================================================================
# V2 Tools Endpoints Tests
# =============================================================================
from __future__ import annotations

from typing import Any

import pytest


@pytest.mark.unit
def test_list_tools_v2(client: Any) -> None:
    """Test listing tools in v2."""
    response = client.get("/api/v2/tools")
    assert response.status_code == 200
    data = response.json()
    assert "tools" in data
    assert "total" in data


@pytest.mark.unit
def test_get_tool_v2(client: Any) -> None:
    """Test getting tool detail in v2."""
    response = client.get("/api/v2/tools/echo")
    assert response.status_code in [200, 404]
