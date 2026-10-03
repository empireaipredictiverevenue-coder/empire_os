from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping

from empire_os.hybrid_compute import Route


REGISTRY_VERSION = "empire-node-registry-v1"


class NodeKind(str, Enum):
    INTELLIGENCE = "intelligence"
    COMPUTE = "compute"
    PREDICTIVE = "predictive"
    DETERMINISTIC = "deterministic"
    OPTIMIZATION = "optimization"
    AGENT = "agent"
    GOVERNANCE = "governance"
    DATA = "data"


class NodeHealth(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"
    OFFLINE = "offline"


class NodeAuthority(str, Enum):
    OBSERVE = "observe"
    ADVISORY = "advisory"
    GOVERNED_EXECUTION = "governed_execution"


@dataclass(frozen=True)
class NodeSpec:
    node_id: str
    kind: NodeKind
    capabilities: frozenset[str]
    routes: frozenset[Route] = frozenset()
    health: NodeHealth = NodeHealth.UNKNOWN
    authority: NodeAuthority = NodeAuthority.OBSERVE
    tenant_namespace_required: bool = False
    provider: str | None = None
    endpoint: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        node_id = self.node_id.strip()

        if not node_id:
            raise ValueError("node_id required")

        if node_id != self.node_id:
            raise ValueError("node_id must be normalized")

        if not self.capabilities:
            raise ValueError("at least one capability required")

        for capability in self.capabilities:
            if not capability or capability != capability.strip():
                raise ValueError("capabilities must be normalized")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["kind"] = self.kind.value
        payload["health"] = self.health.value
        payload["authority"] = self.authority.value
        payload["capabilities"] = sorted(self.capabilities)
        payload["routes"] = sorted(
            route.value for route in self.routes
        )
        payload["metadata"] = dict(self.metadata)
        return payload


class NodeRegistry:
    def __init__(self) -> None:
        self._nodes: dict[str, NodeSpec] = {}

    def register(self, node: NodeSpec) -> None:
        if node.node_id in self._nodes:
            raise ValueError(
                f"duplicate node_id: {node.node_id}"
            )
        self._nodes[node.node_id] = node

    def get(self, node_id: str) -> NodeSpec | None:
        return self._nodes.get(node_id)

    def all(self) -> tuple[NodeSpec, ...]:
        return tuple(
            self._nodes[key]
            for key in sorted(self._nodes)
        )

    def candidates(
        self,
        *,
        capability: str,
        route: Route | None = None,
        tenant_id: str | None = None,
        allow_degraded: bool = False,
    ) -> tuple[NodeSpec, ...]:
        allowed_health = {NodeHealth.HEALTHY}

        if allow_degraded:
            allowed_health.add(NodeHealth.DEGRADED)

        matches: list[NodeSpec] = []

        for node in self._nodes.values():
            if capability not in node.capabilities:
                continue

            if node.health not in allowed_health:
                continue

            if route is not None and route not in node.routes:
                continue

            if (
                node.tenant_namespace_required
                and not tenant_id
            ):
                continue

            matches.append(node)

        return tuple(
            sorted(matches, key=lambda item: item.node_id)
        )

    def snapshot(self) -> dict[str, Any]:
        counts = {
            state.value: 0
            for state in NodeHealth
        }

        for node in self._nodes.values():
            counts[node.health.value] += 1

        return {
            "registry_version": REGISTRY_VERSION,
            "production_authority": False,
            "node_count": len(self._nodes),
            "health": counts,
            "nodes": [
                node.to_dict()
                for node in self.all()
            ],
        }
