"""Deployment planning contracts for Empire Data Cloud.

Plans only. No package install, filesystem mutation, service control, firewall
change, database initialization, credential creation or production deployment.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from empire_os.data_cloud_infrastructure import HostObservation


class DeploymentStage(str, Enum):
    DISCOVERED = "discovered"
    INSTALL_PLAN_READY = "install_plan_ready"
    PRIVATE_NODE_READY = "private_node_ready"
    HA_READY = "ha_ready"
    PRODUCTION_CANDIDATE = "production_candidate"


@dataclass(frozen=True)
class DeploymentTarget:
    postgres_major: int = 18
    private_bind_required: bool = True
    pgbouncer_required: bool = True
    patroni_required_for_ha: bool = True
    pgbackrest_required: bool = True
    public_database_port_allowed: bool = False

    def validate(self) -> None:
        if self.postgres_major != 18:
            raise ValueError("Empire Data Cloud v1 requires PostgreSQL 18")
        if not self.private_bind_required:
            raise ValueError("private database bind is required")
        if self.public_database_port_allowed:
            raise ValueError("public database ports are forbidden")


def build_install_plan(
    observation: HostObservation,
    *,
    target: DeploymentTarget = DeploymentTarget(),
) -> dict[str, Any]:
    """Describe missing components and safety invariants without installing."""

    target.validate()
    missing: list[str] = []
    if not observation.postgres_available:
        missing.append("postgresql")
    if target.pgbouncer_required and not observation.pgbouncer_available:
        missing.append("pgbouncer")
    if target.patroni_required_for_ha and not observation.patroni_available:
        missing.append("patroni")
    if target.pgbackrest_required and not observation.pgbackrest_available:
        missing.append("pgbackrest")

    return {
        "schema_version": "empire.data-cloud-install-plan.v1",
        "stage": DeploymentStage.INSTALL_PLAN_READY.value,
        "target": asdict(target),
        "missing_components": missing,
        "safety": {
            "database_public_port": False,
            "private_bind_required": True,
            "production_deploy": False,
            "service_start": False,
            "database_init": False,
            "credential_creation": False,
        },
    }


def can_be_production_candidate(
    *,
    capacity_ready: bool,
    private_node_verified: bool,
    backup_restore_verified: bool,
    tenant_isolation_verified: bool,
    migration_verification_complete: bool,
) -> bool:
    return all((
        capacity_ready,
        private_node_verified,
        backup_restore_verified,
        tenant_isolation_verified,
        migration_verification_complete,
    ))
