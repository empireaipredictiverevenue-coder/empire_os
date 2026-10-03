from empire_os.node_intelligence_catalog import (
    add_intelligence_nodes,
)
from empire_os.node_registry import (
    NodeAuthority,
    NodeHealth,
    NodeRegistry,
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

    if url.endswith("/health"):
        return {
            "ok": True,
            "service": "search-intelligence-api",
            "mode": "OBSERVE",
            "execution_allowed": False,
        }

    raise AssertionError(url)


def test_registers_all_canonical_nodes():
    r = add_intelligence_nodes(
        NodeRegistry(),
        fetch=fake_fetch,
    )

    assert len(r.all()) == 11


def test_founder_nodes_are_observe_only():
    r = add_intelligence_nodes(
        NodeRegistry(),
        fetch=fake_fetch,
    )

    founder = [
        n
        for n in r.all()
        if n.node_id.startswith(
            "intelligence-node-"
        )
    ]

    assert len(founder) == 10

    assert all(
        n.authority is NodeAuthority.OBSERVE
        for n in founder
    )


def test_active_source_becomes_healthy():
    r = add_intelligence_nodes(
        NodeRegistry(),
        fetch=fake_fetch,
    )

    node = r.get("intelligence-node-0")

    assert node is not None
    assert node.health is NodeHealth.HEALTHY


def test_search_health_is_verified():
    r = add_intelligence_nodes(
        NodeRegistry(),
        fetch=fake_fetch,
    )

    node = r.get("search-intelligence-api")

    assert node is not None
    assert node.health is NodeHealth.HEALTHY

    assert (
        node.metadata[
            "observe_boundary_verified"
        ]
        is True
    )


def test_unknown_lifecycle_fails_closed():
    def fetch(url):
        if "founder-intelligence-nodes" in url:
            return {
                "nodes": [{
                    "key": "future",
                    "lifecycle_state": "experimental",
                    "execution_authority": "none",
                }]
            }

        return fake_fetch(url)

    r = add_intelligence_nodes(
        NodeRegistry(),
        fetch=fetch,
    )

    assert (
        r.get(
            "intelligence-future"
        ).health
        is NodeHealth.UNKNOWN
    )


def test_search_execution_drift_is_degraded():
    def fetch(url):
        if "founder-intelligence-nodes" in url:
            return {
                "nodes": [{
                    "key": "one",
                    "lifecycle_state": "active",
                    "execution_authority": "none",
                }]
            }

        return {
            "ok": True,
            "service": "search-intelligence-api",
            "mode": "EXECUTE",
            "execution_allowed": True,
        }

    r = add_intelligence_nodes(
        NodeRegistry(),
        fetch=fetch,
    )

    assert (
        r.get(
            "search-intelligence-api"
        ).health
        is NodeHealth.DEGRADED
    )
