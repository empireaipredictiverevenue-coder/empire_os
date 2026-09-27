import pytest

from empire_os.data_cloud_deployment import (
    DeploymentTarget,
    build_install_plan,
    can_be_production_candidate,
)
from empire_os.data_cloud_infrastructure import GIB, HostObservation


def _host(**overrides):
    values = {
        "cpu_count": 8,
        "memory_bytes": 16 * GIB,
        "disk_total_bytes": 500 * GIB,
        "disk_free_bytes": 300 * GIB,
        "postgres_available": False,
        "pgbouncer_available": False,
        "patroni_available": False,
        "pgbackrest_available": False,
    }
    values.update(overrides)
    return HostObservation(**values)


def test_install_plan_is_private_and_non_mutating():
    plan = build_install_plan(_host())
    assert plan["missing_components"] == [
        "postgresql",
        "pgbouncer",
        "patroni",
        "pgbackrest",
    ]
    assert plan["safety"]["database_public_port"] is False
    assert plan["safety"]["production_deploy"] is False
    assert plan["safety"]["service_start"] is False
    assert plan["safety"]["database_init"] is False


def test_candidate_requires_every_verification_gate():
    assert can_be_production_candidate(
        capacity_ready=True,
        private_node_verified=True,
        backup_restore_verified=True,
        tenant_isolation_verified=True,
        migration_verification_complete=True,
    ) is True
    assert can_be_production_candidate(
        capacity_ready=True,
        private_node_verified=True,
        backup_restore_verified=False,
        tenant_isolation_verified=True,
        migration_verification_complete=True,
    ) is False


def test_public_database_port_is_rejected():
    with pytest.raises(ValueError, match="public database ports"):
        build_install_plan(
            _host(),
            target=DeploymentTarget(public_database_port_allowed=True),
        )
