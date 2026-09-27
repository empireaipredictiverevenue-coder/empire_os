"""Empire Data Cloud architecture and migration contracts.

Side-effect free. Defines the stable boundary EmpireOS business modules depend
on while the underlying canonical store moves from a vendor-specific backend to
Empire Data Cloud.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class DataBackend(str, Enum):
    SUPABASE_LEGACY = "supabase_legacy"
    EMPIREDB = "empiredb"


class MigrationState(str, Enum):
    DISCOVER = "discover"
    SHADOW = "shadow"
    COPY = "copy"
    VERIFY = "verify"
    DUAL_READ_COMPARE = "dual_read_compare"
    CUTOVER_READY = "cutover_ready"
    FOUNDER_APPROVED_CUTOVER = "founder_approved_cutover"
    EMPIREDB_CANONICAL = "empiredb_canonical"
    SUPABASE_RETIRED = "supabase_retired"


MIGRATION_ORDER = tuple(MigrationState)


@dataclass(frozen=True)
class ApiSurface:
    name: str
    prefix: str
    public_by_default: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


API_SURFACES = (
    ApiSurface("data", "/data/v1/"),
    ApiSurface("graphql", "/graphql/v1/"),
    ApiSurface("rpc", "/rpc/v1/"),
    ApiSurface("vector", "/vector/v1/"),
    ApiSurface("events", "/events/v1/"),
    ApiSurface("auth", "/auth/v1/"),
    ApiSurface("storage", "/storage/v1/"),
    ApiSurface("functions", "/functions/v1/"),
    ApiSurface("ai", "/ai/v1/"),
    ApiSurface("platform", "/platform/v1/"),
    ApiSurface("mcp", "/mcp/v1/"),
)


@dataclass(frozen=True)
class DataCloudAuthority:
    internal_read: bool = True
    internal_write: bool = True
    schema_mutation: bool = False
    destructive_operation: bool = False
    cross_tenant_access: bool = False
    live_outbound: bool = False
    binding_terms: bool = False
    fund_movement: bool = False
    revenue_recognition: bool = False
    authority_expansion: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DataCloudContract:
    schema_version: str = "empire.data-cloud-contract.v1"
    postgres_major: int = 18
    pooler: str = "pgbouncer"
    ha_orchestrator: str = "patroni"
    vector_extension: str = "pgvector"
    tenant_aware: bool = True
    point_in_time_recovery_required: bool = True
    off_node_backup_required: bool = True
    private_database_network_required: bool = True
    vendor_neutral_application_boundary: bool = True

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["api_surfaces"] = [surface.as_dict() for surface in API_SURFACES]
        return payload


def migration_can_advance(
    current: MigrationState,
    target: MigrationState,
    *,
    founder_cutover_approved: bool = False,
) -> bool:
    """Allow only the next state, and preserve the founder cutover gate."""

    current_index = MIGRATION_ORDER.index(current)
    target_index = MIGRATION_ORDER.index(target)

    if target_index != current_index + 1:
        return False

    if target is MigrationState.FOUNDER_APPROVED_CUTOVER:
        return founder_cutover_approved

    return True


def canonical_backend_for_state(state: MigrationState) -> DataBackend:
    """Return the only backend permitted to be described as canonical."""

    if state in {
        MigrationState.EMPIREDB_CANONICAL,
        MigrationState.SUPABASE_RETIRED,
    }:
        return DataBackend.EMPIREDB
    return DataBackend.SUPABASE_LEGACY


def external_api_enabled_by_default() -> bool:
    """External developer-platform exposure remains fail-closed."""

    return any(surface.public_by_default for surface in API_SURFACES)
