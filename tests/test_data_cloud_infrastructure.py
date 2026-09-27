from empire_os.data_cloud_infrastructure import (
    GIB,
    FoundationCapacityPolicy,
    HostObservation,
    evaluate_foundation_readiness,
)


def _host(**overrides):
    values = {
        "cpu_count": 8,
        "memory_bytes": 16 * GIB,
        "disk_total_bytes": 500 * GIB,
        "disk_free_bytes": 300 * GIB,
        "postgres_available": True,
        "pgbouncer_available": True,
        "patroni_available": True,
        "pgbackrest_available": True,
    }
    values.update(overrides)
    return HostObservation(**values)


def test_foundation_capacity_can_be_ready_without_granting_mutation():
    result = evaluate_foundation_readiness(_host())
    assert result["capacity_ready"] is True
    assert result["findings"] == []
    assert result["authority"]["package_install"] is False
    assert result["authority"]["service_mutation"] is False
    assert result["authority"]["database_mutation"] is False
    assert result["authority"]["production_cutover"] is False


def test_low_resources_fail_readiness():
    result = evaluate_foundation_readiness(
        _host(cpu_count=2, memory_bytes=4 * GIB, disk_free_bytes=20 * GIB)
    )
    assert result["capacity_ready"] is False
    assert "cpu_below_foundation_floor" in result["findings"]
    assert "memory_below_foundation_floor" in result["findings"]
    assert "disk_free_below_foundation_floor" in result["findings"]


def test_missing_packages_are_reported_not_installed():
    result = evaluate_foundation_readiness(
        _host(
            postgres_available=False,
            pgbouncer_available=False,
            patroni_available=False,
            pgbackrest_available=False,
        )
    )
    assert result["capacity_ready"] is True
    assert result["missing_packages"] == [
        "postgresql",
        "pgbouncer",
        "patroni",
        "pgbackrest",
    ]


def test_policy_is_explicit_and_replaceable():
    result = evaluate_foundation_readiness(
        _host(cpu_count=2),
        policy=FoundationCapacityPolicy(min_cpu_count=2),
    )
    assert result["capacity_ready"] is True
