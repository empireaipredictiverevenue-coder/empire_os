"""Canonical vendor-neutral data gateway for EmpireOS.

Business modules migrate onto this boundary instead of importing vendor SDKs,
reading vendor credentials, or constructing vendor URLs directly.

The gateway is deliberately single-primary for writes. It never falls back to a
different backend after a failed write because that could create split-brain
commercial truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

from empire_os.data_cloud_contract import DataBackend


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

    def insert(
        self,
        table: str,
        row: Mapping[str, Any],
        *,
        return_repr: bool = True,
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
