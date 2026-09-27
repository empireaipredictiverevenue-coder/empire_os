"""Read-only infrastructure discovery for Empire Data Cloud.

This module measures local host capacity and executable availability only.
It does not install packages, start services, access credentials, connect to a
database, change networking, or mutate production state.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path
import shutil
from typing import Any


GIB = 1024 ** 3


@dataclass(frozen=True)
class HostObservation:
    cpu_count: int
    memory_bytes: int
    disk_total_bytes: int
    disk_free_bytes: int
    postgres_available: bool
    pgbouncer_available: bool
    patroni_available: bool
    pgbackrest_available: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FoundationCapacityPolicy:
    """Conservative minimums for the first EmpireDB production node."""

    min_cpu_count: int = 4
    min_memory_bytes: int = 8 * GIB
    min_free_disk_bytes: int = 50 * GIB


def _read_memory_bytes(meminfo: str | Path = "/proc/meminfo") -> int:
    try:
        for line in Path(meminfo).read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        return 0
    return 0


def observe_local_host(root: str | Path = "/") -> HostObservation:
    """Collect safe capacity evidence from the local host."""

    usage = shutil.disk_usage(Path(root))
    return HostObservation(
        cpu_count=max(0, int(os.cpu_count() or 0)),
        memory_bytes=_read_memory_bytes(),
        disk_total_bytes=int(usage.total),
        disk_free_bytes=int(usage.free),
        postgres_available=shutil.which("psql") is not None,
        pgbouncer_available=shutil.which("pgbouncer") is not None,
        patroni_available=shutil.which("patroni") is not None,
        pgbackrest_available=shutil.which("pgbackrest") is not None,
    )


def evaluate_foundation_readiness(
    observation: HostObservation,
    *,
    policy: FoundationCapacityPolicy = FoundationCapacityPolicy(),
) -> dict[str, Any]:
    findings: list[str] = []

    if observation.cpu_count < policy.min_cpu_count:
        findings.append("cpu_below_foundation_floor")
    if observation.memory_bytes < policy.min_memory_bytes:
        findings.append("memory_below_foundation_floor")
    if observation.disk_free_bytes < policy.min_free_disk_bytes:
        findings.append("disk_free_below_foundation_floor")

    missing_packages = [
        name
        for name, available in (
            ("postgresql", observation.postgres_available),
            ("pgbouncer", observation.pgbouncer_available),
            ("patroni", observation.patroni_available),
            ("pgbackrest", observation.pgbackrest_available),
        )
        if not available
    ]

    return {
        "schema_version": "empire.data-cloud-infrastructure-readiness.v1",
        "capacity_ready": not findings,
        "findings": findings,
        "missing_packages": missing_packages,
        "host": observation.as_dict(),
        "authority": {
            "package_install": False,
            "service_mutation": False,
            "database_mutation": False,
            "network_mutation": False,
            "production_cutover": False,
        },
    }
