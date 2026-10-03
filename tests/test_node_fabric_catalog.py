from empire_os.node_fabric_catalog import (
    build_full_node_registry,
    full_fabric_snapshot,
)
from empire_os.node_registry import (
    NodeAuthority,
)
from empire_os.node_runtime_catalog import (
    ProbeResult,
)


def healthy_probe(endpoint):
    return ProbeResult(
        healthy=True,
        status_code=200,
        endpoint=endpoint,
    )


def fake_fetch(url):
    if "founder-intelligence-nodes" in url:
        return {
            "nodes": [
                {
                    "key": f"node_{i}",
                    "name": f"Node {i}",
                    "lifecycle_state": "active",
                    "execution_authority": "none",
                }
                for i in range(10)
            ]
        }

    return {
        "ok": True,
        "service": "search-intelligence-api",
        "mode": "OBSERVE",
        "execution_allowed": False,
    }


def test_full_fabric_combines_all_layers():
    registry = build_full_node_registry(
        probe=healthy_probe,
        fetch=fake_fetch,
    )

    # 6 runtime/model nodes
    # 3 canonical domain nodes
    # 10 founder intelligence nodes
    # 1 search intelligence node
    assert len(registry.all()) == 20


def test_fabric_never_inherits_authority():
    registry = build_full_node_registry(
        probe=healthy_probe,
        fetch=fake_fetch,
    )

    assert all(
        node.authority
        is NodeAuthority.OBSERVE
        for node in registry.all()
    )


def test_snapshot_exposes_no_execution():
    snapshot = full_fabric_snapshot(
        probe=healthy_probe,
        fetch=fake_fetch,
    )

    assert snapshot["node_count"] == 20

    assert (
        snapshot["production_authority"]
        is False
    )

    assert (
        snapshot["execution_enabled"]
        is False
    )
