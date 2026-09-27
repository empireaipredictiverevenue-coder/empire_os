"""Canonical vendor-neutral data gateway for EmpireOS.

Business modules migrate onto this boundary instead of importing vendor SDKs,
reading vendor credentials, or constructing vendor URLs directly.

The gateway is deliberately single-primary for writes. It never falls back to a
different backend after a failed write because that could create split-brain
commercial truth.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Mapping, Protocol, Sequence

from empire_os.data_cloud_contract import DataBackend
from empire_os.data_query import ConflictAction, DataFilter, OrderSpec


class DataGatewayUnavailable(RuntimeError):
    pass


class DataGatewayOperationUnsupported(RuntimeError):
    pass


class CanonicalDataProvider(Protocol):
    @property
    def backend(self) -> DataBackend:
        ...

    def configured(self) -> bool:
        ...

    def select(
        self,
        table: str,
        columns: str = "*",
        filters: Mapping[str, object] | None = None,
        order: str | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> Sequence[Mapping[str, Any]]:
        ...

    def query(
        self,
        table: str,
        columns: str = "*",
        *,
        filters: Sequence[DataFilter] = (),
        order: Sequence[OrderSpec] = (),
        limit: int = 1000,
        offset: int = 0,
    ) -> Sequence[Mapping[str, Any]]:
        ...

    def count(
        self,
        table: str,
        filters: Mapping[str, object] | None = None,
    ) -> int:
        ...

    def insert(
        self,
        table: str,
        row: Mapping[str, Any],
        *,
        return_repr: bool = True,
    ) -> Sequence[Mapping[str, Any]]:
        ...

    def upsert(
        self,
        table: str,
        row: Mapping[str, Any],
        *,
        conflict_columns: Sequence[str],
        action: ConflictAction,
        return_repr: bool = True,
    ) -> Sequence[Mapping[str, Any]]:
        ...

    def insert_ignore_conflicts(
        self,
        table: str,
        row: Mapping[str, Any],
        *,
        conflict_columns: Sequence[str] = (),
        return_repr: bool = False,
    ) -> Sequence[Mapping[str, Any]]:
        ...

    def update(
        self,
        table: str,
        match: Mapping[str, object],
        values: Mapping[str, Any],
    ) -> Sequence[Mapping[str, Any]]:
        ...

    def delete(
        self,
        table: str,
        match: Mapping[str, object],
    ) -> None:
        ...

    def rpc(
        self,
        name: str,
        params: Mapping[str, Any] | None = None,
    ) -> object:
        ...


@dataclass(frozen=True)
class GatewaySnapshot:
    primary_backend: DataBackend
    configured: bool
    dual_write_enabled: bool = False
    write_fallback_enabled: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": "empire.canonical-data-gateway.v1",
            "primary_backend": self.primary_backend.value,
            "configured": self.configured,
            "dual_write_enabled": self.dual_write_enabled,
            "write_fallback_enabled": self.write_fallback_enabled,
        }


class CanonicalDataGateway:
    """Single-primary provider router for canonical business data."""

    def __init__(
        self,
        provider: CanonicalDataProvider,
        *,
        expected_backend: DataBackend | None = None,
    ) -> None:
        if expected_backend is not None and provider.backend is not expected_backend:
            raise ValueError("provider/backend mismatch")
        self._provider = provider

    @property
    def backend(self) -> DataBackend:
        return self._provider.backend

    @property
    def configured(self) -> bool:
        return bool(self._provider.configured())

    def snapshot(self) -> GatewaySnapshot:
        return GatewaySnapshot(
            primary_backend=self.backend,
            configured=self.configured,
            dual_write_enabled=False,
            write_fallback_enabled=False,
        )

    def _require_provider(self) -> None:
        if not self.configured:
            raise DataGatewayUnavailable(
                f"canonical data backend is not configured: {self.backend.value}"
            )

    def select(
        self,
        table: str,
        columns: str = "*",
        filters: Mapping[str, object] | None = None,
        order: str | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        self._require_provider()
        rows = self._provider.select(
            table,
            columns,
            filters,
            order,
            limit,
            offset,
        )
        return [dict(row) for row in rows]

    def query(
        self,
        table: str,
        columns: str = "*",
        *,
        filters: Sequence[DataFilter] = (),
        order: Sequence[OrderSpec] = (),
        limit: int = 1000,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        self._require_provider()
        rows = self._provider.query(
            table,
            columns,
            filters=filters,
            order=order,
            limit=limit,
            offset=offset,
        )
        return [dict(row) for row in rows]

    def count(
        self,
        table: str,
        filters: Mapping[str, object] | None = None,
    ) -> int:
        self._require_provider()
        return int(self._provider.count(table, filters))

    def insert(
        self,
        table: str,
        row: Mapping[str, Any],
        *,
        return_repr: bool = True,
    ) -> list[dict[str, Any]]:
        self._require_provider()
        rows = self._provider.insert(
            table,
            row,
            return_repr=return_repr,
        )
        return [dict(item) for item in rows]

    def upsert(
        self,
        table: str,
        row: Mapping[str, Any],
        *,
        conflict_columns: Sequence[str],
        action: ConflictAction,
        return_repr: bool = True,
    ) -> list[dict[str, Any]]:
        self._require_provider()
        rows = self._provider.upsert(
            table,
            row,
            conflict_columns=conflict_columns,
            action=action,
            return_repr=return_repr,
        )
        return [dict(item) for item in rows]

    def insert_ignore_conflicts(
        self,
        table: str,
        row: Mapping[str, Any],
        *,
        conflict_columns: Sequence[str] = (),
        return_repr: bool = False,
    ) -> list[dict[str, Any]]:
        self._require_provider()
        rows = self._provider.insert_ignore_conflicts(
            table,
            row,
            conflict_columns=conflict_columns,
            return_repr=return_repr,
        )
        return [dict(item) for item in rows]

    def update(
        self,
        table: str,
        match: Mapping[str, object],
        values: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        self._require_provider()
        rows = self._provider.update(table, match, values)
        return [dict(item) for item in rows]

    def delete(
        self,
        table: str,
        match: Mapping[str, object],
    ) -> None:
        self._require_provider()
        self._provider.delete(table, match)

    def rpc(
        self,
        name: str,
        params: Mapping[str, Any] | None = None,
    ) -> object:
        self._require_provider()
        return self._provider.rpc(name, params)



def gateway_from_environment(
    environ: Mapping[str, str] | None = None,
    *,
    legacy_provider_factory: Any | None = None,
    empiredb_provider_factory: Any | None = None,
) -> CanonicalDataGateway:
    """Build the canonical gateway from explicit backend selection.

    Default remains the currently canonical legacy backend during migration.
    Selecting EmpireDB before its verified provider is registered fails closed.
    """

    source = os.environ if environ is None else environ
    raw_backend = str(
        source.get("EMPIRE_DATA_BACKEND")
        or DataBackend.SUPABASE_LEGACY.value
    ).strip()

    try:
        backend = DataBackend(raw_backend)
    except ValueError as exc:
        raise DataGatewayUnavailable(
            f"unsupported canonical data backend: {raw_backend}"
        ) from exc

    if backend is DataBackend.EMPIREDB:
        try:
            if empiredb_provider_factory is None:
                from empire_os.data_backends.empiredb import EmpireDbProvider
                from empire_os.data_backends.postgres import (
                    PostgresConnectionConfig,
                    PostgresConnector,
                )

                provider = EmpireDbProvider(
                    PostgresConnector(
                        PostgresConnectionConfig.from_env(source)
                    )
                )
            else:
                provider = empiredb_provider_factory(source)
        except (ValueError, RuntimeError) as exc:
            raise DataGatewayUnavailable(
                "EmpireDB selected but its runtime provider is not configured"
            ) from exc

        return CanonicalDataGateway(
            provider,
            expected_backend=DataBackend.EMPIREDB,
        )

    if legacy_provider_factory is None:
        from empire_os.data_backends.supabase_legacy import (
            SupabaseLegacyConfig,
            SupabaseLegacyProvider,
        )

        provider = SupabaseLegacyProvider(
            SupabaseLegacyConfig(
                url=str(source.get("SUPABASE_URL") or ""),
                service_key=str(source.get("SUPABASE_SERVICE_KEY") or ""),
            )
        )
    else:
        provider = legacy_provider_factory(source)

    return CanonicalDataGateway(
        provider,
        expected_backend=DataBackend.SUPABASE_LEGACY,
    )
