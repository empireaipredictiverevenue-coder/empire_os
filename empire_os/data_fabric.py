"""Vendor-neutral Empire Data Fabric interfaces.

This module contains routing and authority contracts only. It deliberately does
not open network connections or mutate a database.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping, Protocol, Sequence

from empire_os.data_cloud_contract import (
    DataBackend,
    MigrationState,
    canonical_backend_for_state,
)


class DataOperation(str, Enum):
    READ = "read"
    WRITE = "write"
    APPEND_EVENT = "append_event"
    VECTOR_SEARCH = "vector_search"


class DataScope(str, Enum):
    TENANT = "tenant"
    PLATFORM = "platform"


@dataclass(frozen=True)
class DataRequestContext:
    actor_id: str
    operation: DataOperation
    scope: DataScope = DataScope.TENANT
    tenant_id: str | None = None
    correlation_id: str | None = None

    def __post_init__(self) -> None:
        if not self.actor_id.strip():
            raise ValueError("actor_id is required")
        if self.scope is DataScope.TENANT and not (self.tenant_id or "").strip():
            raise ValueError("tenant_id is required for tenant-scoped data access")


@dataclass(frozen=True)
class DataRoutePlan:
    primary: DataBackend
    shadow_reads: tuple[DataBackend, ...] = ()
    dual_write: bool = False

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["primary"] = self.primary.value
        payload["shadow_reads"] = [backend.value for backend in self.shadow_reads]
        return payload


def route_for_migration_state(
    state: MigrationState,
    operation: DataOperation,
) -> DataRoutePlan:
    """Resolve backend routing without introducing split-brain writes.

    During DUAL_READ_COMPARE, reads may be compared against EmpireDB while the
    canonical result still comes from Supabase. Writes remain single-primary
    until EmpireDB has become canonical.
    """

    primary = canonical_backend_for_state(state)

    if (
        state is MigrationState.DUAL_READ_COMPARE
        and operation in {
            DataOperation.READ,
            DataOperation.VECTOR_SEARCH,
        }
    ):
        return DataRoutePlan(
            primary=DataBackend.SUPABASE_LEGACY,
            shadow_reads=(DataBackend.EMPIREDB,),
            dual_write=False,
        )

    return DataRoutePlan(
        primary=primary,
        shadow_reads=(),
        dual_write=False,
    )


@dataclass(frozen=True)
class DataBackendHealth:
    backend: DataBackend
    healthy: bool
    read_ready: bool
    write_ready: bool
    observed_at: str
    detail: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["backend"] = self.backend.value
        return payload


class DataFabricBackend(Protocol):
    """Minimum backend contract implemented by vendor adapters."""

    @property
    def backend(self) -> DataBackend:
        ...

    def health(self) -> DataBackendHealth:
        ...

    def read(
        self,
        *,
        context: DataRequestContext,
        resource: str,
        parameters: Mapping[str, Any],
    ) -> Sequence[Mapping[str, Any]]:
        ...

    def write(
        self,
        *,
        context: DataRequestContext,
        resource: str,
        values: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        ...

    def append_event(
        self,
        *,
        context: DataRequestContext,
        event_type: str,
        payload: Mapping[str, Any],
        evidence_refs: Sequence[str] = (),
    ) -> Mapping[str, Any]:
        ...


def shadow_compare_allowed(
    context: DataRequestContext,
    plan: DataRoutePlan,
) -> bool:
    """Shadow comparison is read-only and never authorizes a second write."""

    return (
        context.operation in {DataOperation.READ, DataOperation.VECTOR_SEARCH}
        and bool(plan.shadow_reads)
        and plan.dual_write is False
    )
