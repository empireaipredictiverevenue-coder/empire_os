"""Topology contracts for Empire Data Cloud."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Sequence


class NodeRole(str, Enum):
    PRIMARY = "primary"
    SYNC_REPLICA = "sync_replica"
    READ_REPLICA = "read_replica"
    DR_REPLICA = "dr_replica"


@dataclass(frozen=True)
class DataNode:
    node_id: str
    role: NodeRole
    region: str
    healthy: bool
    replication_lag_seconds: float | None = None
    writable: bool = False

    def validate(self) -> None:
        if not self.node_id.strip() or not self.region.strip():
            raise ValueError("node identity and region are required")
        if self.role is NodeRole.PRIMARY and not self.writable:
            raise ValueError("primary must be writable")
        if self.role is not NodeRole.PRIMARY and self.writable:
            raise ValueError("replicas must not be writable")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        payload = asdict(self)
        payload["role"] = self.role.value
        return payload


def validate_topology(nodes: Sequence[DataNode]) -> None:
    for node in nodes:
        node.validate()
    primaries = [node for node in nodes if node.role is NodeRole.PRIMARY]
    if len(primaries) != 1:
        raise ValueError("topology requires exactly one primary")
