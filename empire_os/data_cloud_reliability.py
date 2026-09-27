"""Read-only reliability evaluation for Empire Data Cloud."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence

from empire_os.data_cloud_topology import DataNode, NodeRole, validate_topology


@dataclass(frozen=True)
class BackupState:
    last_success_age_seconds: float | None
    off_node: bool
    encrypted: bool
    restore_verified: bool
    pitr_ready: bool


@dataclass(frozen=True)
class ReliabilityPolicy:
    max_sync_replica_lag_seconds: float = 10.0
    max_dr_replica_lag_seconds: float = 300.0
    max_backup_age_seconds: float = 86400.0


def evaluate_reliability(
    nodes: Sequence[DataNode],
    backup: BackupState,
    *,
    policy: ReliabilityPolicy = ReliabilityPolicy(),
) -> dict[str, Any]:
    validate_topology(nodes)
    findings: list[str] = []

    primary = next(n for n in nodes if n.role is NodeRole.PRIMARY)
    sync = [n for n in nodes if n.role is NodeRole.SYNC_REPLICA]
    dr = [n for n in nodes if n.role is NodeRole.DR_REPLICA]

    if not primary.healthy:
        findings.append(f"primary_unhealthy:{primary.node_id}")
    if not sync:
        findings.append("sync_replica_missing")
    if not dr:
        findings.append("dr_replica_missing")

    for node in sync:
        if not node.healthy:
            findings.append(f"sync_replica_unhealthy:{node.node_id}")
        if (
            node.replication_lag_seconds is None
            or node.replication_lag_seconds > policy.max_sync_replica_lag_seconds
        ):
            findings.append(f"sync_replica_lag:{node.node_id}")

    for node in dr:
        if not node.healthy:
            findings.append(f"dr_replica_unhealthy:{node.node_id}")
        if (
            node.replication_lag_seconds is None
            or node.replication_lag_seconds > policy.max_dr_replica_lag_seconds
        ):
            findings.append(f"dr_replica_lag:{node.node_id}")

    if not backup.off_node:
        findings.append("backup_not_off_node")
    if not backup.encrypted:
        findings.append("backup_not_encrypted")
    if not backup.restore_verified:
        findings.append("restore_not_verified")
    if not backup.pitr_ready:
        findings.append("pitr_not_ready")
    if (
        backup.last_success_age_seconds is None
        or backup.last_success_age_seconds > policy.max_backup_age_seconds
    ):
        findings.append("backup_stale")

    return {
        "schema_version": "empire.data-cloud-reliability.v1",
        "healthy": not findings,
        "findings": findings,
        "backup": asdict(backup),
        "authority": {
            "automatic_failover_execution": False,
            "destructive_repair": False,
            "schema_mutation": False,
        },
    }
