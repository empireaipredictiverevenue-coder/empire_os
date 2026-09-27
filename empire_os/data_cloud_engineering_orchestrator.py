"""Parallel engineering orchestration contract for Empire Data Cloud.

This module describes bounded engineering lanes. It does not execute workers,
write production data, deploy infrastructure, or grant consequential authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class EngineeringLane:
    key: str
    capability: str
    preferred_worker: str
    allowed_paths: tuple[str, ...]
    required_tests: tuple[str, ...]
    risk_class: str = "medium"
    authority: str = "internal_write"
    independent_verifier: str = "swarm_v6"

    def validate(self) -> None:
        if not self.key.strip():
            raise ValueError("lane key required")
        if not self.allowed_paths:
            raise ValueError("lane paths required")
        if self.authority != "internal_write":
            raise ValueError("Data Cloud build lanes are repository-write only")
        for path in self.allowed_paths:
            if path.startswith(("recovery/", "toop/", "/")) or ".." in path.split("/"):
                raise ValueError("unsafe lane path")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


def default_data_cloud_lanes() -> tuple[EngineeringLane, ...]:
    lanes = (
        EngineeringLane(
            key="core",
            capability="backend_code",
            preferred_worker="hermes",
            allowed_paths=(
                "empire_os/data_cloud_contract.py",
                "empire_os/data_fabric.py",
                "empire_os/data_backends/",
                "tests/test_data_cloud_contract.py",
                "tests/test_data_fabric.py",
            ),
            required_tests=(
                "tests/test_data_cloud_contract.py",
                "tests/test_data_fabric.py",
            ),
        ),
        EngineeringLane(
            key="migration",
            capability="parallel_backend_code",
            preferred_worker="pi",
            allowed_paths=(
                "empire_os/data_cloud_migration.py",
                "empire_os/data_cloud_discovery.py",
                "tests/test_data_cloud_migration.py",
                "tests/test_data_cloud_discovery.py",
            ),
            required_tests=(
                "tests/test_data_cloud_migration.py",
                "tests/test_data_cloud_discovery.py",
            ),
        ),
        EngineeringLane(
            key="reliability",
            capability="backend_code",
            preferred_worker="hermes",
            allowed_paths=(
                "empire_os/data_cloud_reliability.py",
                "empire_os/data_cloud_topology.py",
                "tests/test_data_cloud_reliability.py",
                "tests/test_data_cloud_topology.py",
            ),
            required_tests=(
                "tests/test_data_cloud_reliability.py",
                "tests/test_data_cloud_topology.py",
            ),
        ),
        EngineeringLane(
            key="api",
            capability="parallel_backend_code",
            preferred_worker="pi",
            allowed_paths=(
                "empire_os/data_cloud_api.py",
                "empire_os/data_cloud_control_plane.py",
                "tests/test_data_cloud_api.py",
                "tests/test_data_cloud_control_plane.py",
            ),
            required_tests=(
                "tests/test_data_cloud_api.py",
                "tests/test_data_cloud_control_plane.py",
            ),
        ),
        EngineeringLane(
            key="security",
            capability="backend_code",
            preferred_worker="empire_coder",
            allowed_paths=(
                "empire_os/data_cloud_security.py",
                "empire_os/data_cloud_tenancy.py",
                "tests/test_data_cloud_security.py",
                "tests/test_data_cloud_tenancy.py",
            ),
            required_tests=(
                "tests/test_data_cloud_security.py",
                "tests/test_data_cloud_tenancy.py",
            ),
        ),
    )
    for lane in lanes:
        lane.validate()
    return lanes


def lanes_have_non_overlapping_ownership(
    lanes: tuple[EngineeringLane, ...] | None = None,
) -> bool:
    """Require unique exact file ownership across mutation lanes."""

    selected = lanes or default_data_cloud_lanes()
    seen: set[str] = set()
    for lane in selected:
        for path in lane.allowed_paths:
            normalized = path.rstrip("/")
            if normalized in seen:
                return False
            seen.add(normalized)
    return True


def engineering_authority_contract() -> dict[str, bool]:
    return {
        "production_deploy": False,
        "canonical_data_write": False,
        "schema_mutation": False,
        "external_send": False,
        "fund_movement": False,
        "revenue_recognition": False,
        "authority_expansion": False,
        "independent_verification_required": True,
        "single_integration_owner_required": True,
    }
