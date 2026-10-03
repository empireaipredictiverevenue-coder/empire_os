import pytest

from empire_os.hybrid_compute import Route
from empire_os.node_registry import (
    NodeAuthority,
    NodeHealth,
    NodeKind,
    NodeRegistry,
    NodeSpec,
)


def node(
    node_id="local-small-1",
    *,
    health=NodeHealth.HEALTHY,
    tenant_required=False,
):
    return NodeSpec(
        node_id=node_id,
        kind=NodeKind.COMPUTE,
        capabilities=frozenset(
            {"compute.local.small"}
        ),
        routes=frozenset({Route.LOCAL_SMALL}),
        health=health,
        authority=NodeAuthority.OBSERVE,
        tenant_namespace_required=tenant_required,
    )


def test_register_and_get():
    registry = NodeRegistry()
    registry.register(node())
    assert registry.get("local-small-1") is not None


def test_duplicate_node_fails_closed():
    registry = NodeRegistry()
    registry.register(node())

    with pytest.raises(ValueError):
        registry.register(node())


def test_empty_capabilities_rejected():
    with pytest.raises(ValueError):
        NodeSpec(
            node_id="bad",
            kind=NodeKind.COMPUTE,
            capabilities=frozenset(),
        )


def test_healthy_candidate_resolves():
    registry = NodeRegistry()
    registry.register(node())

    result = registry.candidates(
        capability="compute.local.small",
        route=Route.LOCAL_SMALL,
    )

    assert len(result) == 1


def test_offline_node_not_candidate():
    registry = NodeRegistry()
    registry.register(
        node(health=NodeHealth.OFFLINE)
    )

    assert not registry.candidates(
        capability="compute.local.small",
        route=Route.LOCAL_SMALL,
    )


def test_unknown_node_not_candidate():
    registry = NodeRegistry()
    registry.register(
        node(health=NodeHealth.UNKNOWN)
    )

    assert not registry.candidates(
        capability="compute.local.small",
        route=Route.LOCAL_SMALL,
    )


def test_degraded_requires_explicit_policy():
    registry = NodeRegistry()
    registry.register(
        node(health=NodeHealth.DEGRADED)
    )

    assert not registry.candidates(
        capability="compute.local.small",
        route=Route.LOCAL_SMALL,
    )

    assert registry.candidates(
        capability="compute.local.small",
        route=Route.LOCAL_SMALL,
        allow_degraded=True,
    )


def test_tenant_scoped_node_requires_tenant():
    registry = NodeRegistry()
    registry.register(
        node(tenant_required=True)
    )

    assert not registry.candidates(
        capability="compute.local.small",
        route=Route.LOCAL_SMALL,
    )

    assert registry.candidates(
        capability="compute.local.small",
        route=Route.LOCAL_SMALL,
        tenant_id="tenant-a",
    )


def test_snapshot_has_zero_authority():
    registry = NodeRegistry()
    registry.register(node())

    result = registry.snapshot()

    assert result["production_authority"] is False
    assert result["node_count"] == 1
