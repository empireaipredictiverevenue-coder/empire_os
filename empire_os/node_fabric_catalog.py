from __future__ import annotations

from typing import Any

from empire_os.node_domain_catalog import (
    add_domain_nodes,
)
from empire_os.node_intelligence_catalog import (
    FetchJson,
    add_intelligence_nodes,
    fetch_json,
)
from empire_os.node_registry import (
    NodeKind,
    NodeRegistry,
)
from empire_os.node_runtime_catalog import (
    Probe,
    build_runtime_registry,
    probe_http,
)


FABRIC_VERSION = "empire-node-fabric-v2.1"


def build_full_node_registry(
    *,
    probe: Probe = probe_http,
    fetch: FetchJson = fetch_json,
) -> NodeRegistry:
    registry = build_runtime_registry(
        probe=probe
    )

    add_domain_nodes(registry)

    add_intelligence_nodes(
        registry,
        fetch=fetch,
    )

    return registry


def full_fabric_snapshot(
    *,
    probe: Probe = probe_http,
    fetch: FetchJson = fetch_json,
) -> dict[str, Any]:
    registry = build_full_node_registry(
        probe=probe,
        fetch=fetch,
    )

    payload = registry.snapshot()

    kinds = {
        kind.value: 0
        for kind in NodeKind
    }

    for node in registry.all():
        kinds[node.kind.value] += 1

    payload.update({
        "fabric_version": FABRIC_VERSION,
        "kind_counts": kinds,
        "production_authority": False,
        "execution_enabled": False,
    })

    return payload
