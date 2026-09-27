"""Deterministic sizing and deployment manifest for EmpireDB Node 1.

The first node is deliberately conservative because it is co-located with
EmpireOS application workloads. Values are starting points, not autonomous
runtime tuning decisions.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


GIB = 1024 ** 3


@dataclass(frozen=True)
class Node1Host:
    cpu_count: int
    memory_gib: float
    disk_free_gib: float
    current_database_gib: float
    colocated_workloads: bool = True

    def validate(self) -> None:
        if self.cpu_count < 1:
            raise ValueError("cpu_count must be positive")
        if self.memory_gib <= 0:
            raise ValueError("memory_gib must be positive")
        if self.disk_free_gib <= 0:
            raise ValueError("disk_free_gib must be positive")
        if self.current_database_gib < 0:
            raise ValueError("current_database_gib cannot be negative")


@dataclass(frozen=True)
class Node1Sizing:
    postgres_major: int
    shared_buffers_gib: int
    effective_cache_size_gib: int
    work_mem_mb: int
    maintenance_work_mem_mb: int
    max_connections: int
    max_worker_processes: int
    max_parallel_workers: int
    max_parallel_workers_per_gather: int
    max_wal_size_gib: int
    min_wal_size_gib: int
    pgbouncer_pool_mode: str
    pgbouncer_listen_port: int
    postgres_listen_port: int
    pgbouncer_max_client_conn: int
    pgbouncer_default_pool_size: int
    pgbouncer_reserve_pool_size: int
    patroni_activate: bool
    pgbackrest_activate: bool
    database_public_port: bool
    minimum_disk_reserve_gib: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def size_node1(host: Node1Host) -> Node1Sizing:
    host.validate()

    if host.cpu_count < 4 or host.memory_gib < 8 or host.disk_free_gib < 50:
        raise ValueError("host is below EmpireDB Node 1 production floor")

    # Cap shared memory aggressively because EmpireOS, workers and local models
    # share this machine. effective_cache_size is planner guidance, not reserved
    # memory.
    shared_buffers = max(2, min(8, int(host.memory_gib * 0.15)))
    effective_cache = max(
        shared_buffers * 2,
        min(32, int(host.memory_gib * 0.50)),
    )

    workers = min(max(4, host.cpu_count), 8)

    return Node1Sizing(
        postgres_major=18,
        shared_buffers_gib=shared_buffers,
        effective_cache_size_gib=effective_cache,
        work_mem_mb=8,
        maintenance_work_mem_mb=1024,
        max_connections=120,
        max_worker_processes=workers,
        max_parallel_workers=workers,
        max_parallel_workers_per_gather=min(4, workers),
        max_wal_size_gib=4,
        min_wal_size_gib=1,
        # Start in session mode to preserve existing session semantics while
        # callers are decoupled from Supabase. Eligible services can move to
        # transaction pooling after compatibility tests.
        pgbouncer_pool_mode="session",
        pgbouncer_listen_port=6432,
        postgres_listen_port=5432,
        pgbouncer_max_client_conn=500,
        pgbouncer_default_pool_size=20,
        pgbouncer_reserve_pool_size=5,
        # A one-node Patroni cluster does not provide HA. Install/readiness may
        # be prepared, but activation waits for a second failure-domain node.
        patroni_activate=False,
        # Backup activation waits for a verified off-node repository target.
        pgbackrest_activate=False,
        database_public_port=False,
        minimum_disk_reserve_gib=max(100, int(host.disk_free_gib * 0.25)),
    )


def node1_manifest(
    host: Node1Host,
) -> dict[str, Any]:
    sizing = size_node1(host)
    packages = (
        "postgresql-18",
        "postgresql-client-18",
        "pgbouncer",
        "pgbackrest",
        "postgresql-18-pgvector",
        "postgresql-18-postgis-3",
    )
    return {
        "schema_version": "empire.data-cloud-node1-manifest.v1",
        "host": asdict(host),
        "sizing": sizing.as_dict(),
        "packages": list(packages),
        "postgresql": {
            "listen_addresses": "127.0.0.1",
            "port": sizing.postgres_listen_port,
            "password_encryption": "scram-sha-256",
            "wal_level": "replica",
            "archive_mode": False,
            "hot_standby": True,
            "max_wal_senders": 10,
            "max_replication_slots": 10,
            "shared_preload_libraries": ["pg_stat_statements"],
            "track_io_timing": True,
            "log_min_duration_statement_ms": 500,
            "log_lock_waits": True,
            "checkpoint_completion_target": 0.9,
        },
        "pgbouncer": {
            "listen_addr": "127.0.0.1",
            "listen_port": sizing.pgbouncer_listen_port,
            "pool_mode": sizing.pgbouncer_pool_mode,
            "max_client_conn": sizing.pgbouncer_max_client_conn,
            "default_pool_size": sizing.pgbouncer_default_pool_size,
            "reserve_pool_size": sizing.pgbouncer_reserve_pool_size,
            "auth_type": "scram-sha-256",
        },
        "activation_gates": {
            "package_install_approved": False,
            "database_init_approved": False,
            "database_service_start_approved": False,
            "off_node_backup_target_verified": False,
            "wal_archiving_activation_approved": False,
            "patroni_second_node_verified": False,
            "canonical_cutover_approved": False,
        },
        "authority": {
            "package_install": False,
            "database_init": False,
            "service_start": False,
            "network_change": False,
            "canonical_cutover": False,
        },
    }
