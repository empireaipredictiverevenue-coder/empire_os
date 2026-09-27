import pytest

from empire_os.data_cloud_node1 import Node1Host, node1_manifest, size_node1


def _host(**changes):
    values = {
        "cpu_count": 8,
        "memory_gib": 62.74,
        "disk_free_gib": 795.95,
        "current_database_gib": 0.35,
        "colocated_workloads": True,
    }
    values.update(changes)
    return Node1Host(**values)


def test_real_empire_host_gets_conservative_node1_profile():
    sizing = size_node1(_host())

    assert sizing.postgres_major == 18
    assert sizing.shared_buffers_gib == 8
    assert sizing.effective_cache_size_gib == 31
    assert sizing.work_mem_mb == 8
    assert sizing.max_connections == 120
    assert sizing.pgbouncer_pool_mode == "session"
    assert sizing.patroni_activate is False
    assert sizing.pgbackrest_activate is False
    assert sizing.database_public_port is False
    assert sizing.minimum_disk_reserve_gib >= 100


def test_manifest_is_private_and_requires_explicit_activation():
    manifest = node1_manifest(_host())

    assert manifest["postgresql"]["listen_addresses"] == "127.0.0.1"
    assert manifest["pgbouncer"]["listen_addr"] == "127.0.0.1"
    assert manifest["pgbouncer"]["auth_type"] == "scram-sha-256"
    assert manifest["postgresql"]["archive_mode"] is False
    assert manifest["activation_gates"]["wal_archiving_activation_approved"] is False
    assert manifest["activation_gates"]["database_init_approved"] is False
    assert manifest["activation_gates"]["canonical_cutover_approved"] is False
    assert manifest["authority"]["service_start"] is False


def test_pgvector_and_postgis_are_in_install_manifest():
    packages = node1_manifest(_host())["packages"]
    assert "postgresql-18-pgvector" in packages
    assert "postgresql-18-postgis-3" in packages


def test_undersized_host_is_rejected():
    with pytest.raises(ValueError, match="below EmpireDB"):
        size_node1(
            _host(cpu_count=2, memory_gib=4, disk_free_gib=20)
        )
