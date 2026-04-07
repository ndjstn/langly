from app.v3.registry import SmallModelRegistry


def test_registry_roles() -> None:
    registry = SmallModelRegistry()
    roles = registry.roles()
    assert "router" in roles
    assert registry.resolve("router")
