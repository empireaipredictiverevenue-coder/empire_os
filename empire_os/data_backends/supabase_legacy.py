"""Legacy Supabase provider behind the Canonical Data Gateway.

This adapter exists only for migration compatibility. New EmpireOS business
logic should depend on CanonicalDataGateway, not on this module.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Mapping, Sequence
import urllib.parse
import urllib.request

from empire_os.data_cloud_contract import DataBackend
from empire_os.data_query import ConflictAction, DataFilter, FilterOperator, OrderSpec


_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _ident(value: str) -> str:
    if not _IDENT.fullmatch(value):
        raise ValueError(f"unsafe query identifier: {value!r}")
    return value


def _columns(value: str) -> str:
    if value == "*":
        return "*"
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if not parts:
        raise ValueError("at least one column is required")
    return ",".join(_ident(part) for part in parts)


def _postgrest_scalar(value: object) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    return str(value)


def _filter_param(item: DataFilter) -> tuple[str, str]:
    column = _ident(item.column)
    if item.operator is FilterOperator.EQ:
        return column, f"eq.{_postgrest_scalar(item.value)}"
    if item.operator is FilterOperator.IS_NULL:
        return column, "is.null"
    if item.operator is FilterOperator.IN:
        values = tuple(item.value or ())
        if not values:
            raise ValueError("IN filter requires at least one value")
        encoded = ",".join(_postgrest_scalar(value) for value in values)
        return column, f"in.({encoded})"
    raise ValueError(f"unsupported filter operator: {item.operator}")


@dataclass(frozen=True)
class SupabaseLegacyConfig:
    url: str
    service_key: str
    timeout_seconds: int = 30

    def validate(self) -> None:
        if bool(self.url.strip()) != bool(self.service_key.strip()):
            raise ValueError("legacy Supabase URL and service key must be configured together")
        if self.timeout_seconds < 1:
            raise ValueError("timeout_seconds must be positive")

    def safe_snapshot(self) -> dict[str, object]:
        self.validate()
        return {
            "backend": DataBackend.SUPABASE_LEGACY.value,
            "configured": bool(self.url.strip() and self.service_key.strip()),
            "timeout_seconds": self.timeout_seconds,
        }


class SupabaseLegacyProvider:
    backend = DataBackend.SUPABASE_LEGACY

    def __init__(
        self,
        config: SupabaseLegacyConfig,
        *,
        urlopen: Any = urllib.request.urlopen,
        aliases: Mapping[str, str] | None = None,
    ) -> None:
        config.validate()
        self._config = config
        self._urlopen = urlopen
        self._aliases = dict(aliases or {})

    def configured(self) -> bool:
        return bool(
            self._config.url.strip()
            and self._config.service_key.strip()
        )

    def _table(self, table: str) -> str:
        return self._aliases.get(table, table)

    def _headers(self, extra: Mapping[str, str] | None = None) -> dict[str, str]:
        headers = {
            "apikey": self._config.service_key,
            "Authorization": f"Bearer {self._config.service_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if extra:
            headers.update(extra)
        return headers

    def _url(self, table: str, query: str = "") -> str:
        return (
            f"{self._config.url.rstrip('/')}/rest/v1/"
            f"{self._table(table)}{query}"
        )

    def select(
        self,
        table: str,
        columns: str = "*",
        filters: Mapping[str, object] | None = None,
        order: str | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> Sequence[Mapping[str, Any]]:
        params: list[tuple[str, str]] = [("select", columns)]
        if filters:
            params.extend((str(k), f"eq.{v}") for k, v in filters.items())
        if order:
            params.append(("order", order))
        params.extend((("offset", str(offset)), ("limit", str(limit))))
        query = "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(
            self._url(table, query),
            headers=self._headers(),
        )
        with self._urlopen(req, timeout=self._config.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

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
        params: list[tuple[str, str]] = [("select", _columns(columns))]
        params.extend(_filter_param(item) for item in filters)
        if order:
            params.append((
                "order",
                ",".join(
                    f"{_ident(item.column)}.{('desc' if item.descending else 'asc')}"
                    for item in order
                ),
            ))
        params.extend((
            ("offset", str(max(0, int(offset)))),
            ("limit", str(max(0, min(int(limit), 10000)))),
        ))
        query = "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(
            self._url(table, query),
            headers=self._headers(),
        )
        with self._urlopen(req, timeout=self._config.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def count(
        self,
        table: str,
        filters: Mapping[str, object] | None = None,
    ) -> int:
        params: list[tuple[str, str]] = [("select", "*"), ("limit", "1")]
        if filters:
            params.extend((str(k), f"eq.{v}") for k, v in filters.items())
        query = "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(
            self._url(table, query),
            headers=self._headers({"Prefer": "count=exact"}),
        )
        with self._urlopen(req, timeout=self._config.timeout_seconds) as response:
            content_range = response.headers.get("Content-Range", "")
            if "/" not in content_range:
                raise RuntimeError("exact count missing Content-Range")
            total = content_range.rsplit("/", 1)[1]
            if not total.isdigit():
                raise RuntimeError("exact count invalid Content-Range")
            return int(total)

    def insert(
        self,
        table: str,
        row: Mapping[str, Any],
        *,
        return_repr: bool = True,
    ) -> Sequence[Mapping[str, Any]]:
        prefer = "return=representation" if return_repr else "return=minimal"
        req = urllib.request.Request(
            self._url(table),
            data=json.dumps(dict(row)).encode("utf-8"),
            headers=self._headers({"Prefer": prefer}),
            method="POST",
        )
        with self._urlopen(req, timeout=self._config.timeout_seconds) as response:
            if not return_repr:
                return ()
            return json.loads(response.read().decode("utf-8"))

    def upsert(
        self,
        table: str,
        row: Mapping[str, Any],
        *,
        conflict_columns: Sequence[str],
        action: ConflictAction,
        return_repr: bool = True,
    ) -> Sequence[Mapping[str, Any]]:
        if not row:
            raise ValueError("upsert row cannot be empty")
        columns = tuple(_ident(str(column)) for column in conflict_columns)
        if not columns:
            raise ValueError("upsert requires conflict columns")

        query = "?" + urllib.parse.urlencode(
            {"on_conflict": ",".join(columns)}
        )
        resolution = (
            "merge-duplicates"
            if action is ConflictAction.MERGE
            else "ignore-duplicates"
        )
        returning = "representation" if return_repr else "minimal"
        req = urllib.request.Request(
            self._url(table, query),
            data=json.dumps(dict(row)).encode("utf-8"),
            headers=self._headers({
                "Prefer": f"resolution={resolution},return={returning}"
            }),
            method="POST",
        )
        with self._urlopen(req, timeout=self._config.timeout_seconds) as response:
            if not return_repr:
                return ()
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else ()

    def insert_ignore_conflicts(
        self,
        table: str,
        row: Mapping[str, Any],
        *,
        return_repr: bool = False,
    ) -> Sequence[Mapping[str, Any]]:
        if not row:
            raise ValueError("insert row cannot be empty")
        returning = "representation" if return_repr else "minimal"
        req = urllib.request.Request(
            self._url(table),
            data=json.dumps(dict(row)).encode("utf-8"),
            headers=self._headers({
                "Prefer": f"resolution=ignore-duplicates,return={returning}"
            }),
            method="POST",
        )
        with self._urlopen(req, timeout=self._config.timeout_seconds) as response:
            if not return_repr:
                return ()
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else ()

    def update(
        self,
        table: str,
        match: Mapping[str, object],
        values: Mapping[str, Any],
    ) -> Sequence[Mapping[str, Any]]:
        query = "?" + urllib.parse.urlencode(
            [(str(k), f"eq.{v}") for k, v in match.items()]
        )
        req = urllib.request.Request(
            self._url(table, query),
            data=json.dumps(dict(values)).encode("utf-8"),
            headers=self._headers({"Prefer": "return=representation"}),
            method="PATCH",
        )
        with self._urlopen(req, timeout=self._config.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def delete(
        self,
        table: str,
        match: Mapping[str, object],
    ) -> None:
        query = "?" + urllib.parse.urlencode(
            [(str(k), f"eq.{v}") for k, v in match.items()]
        )
        req = urllib.request.Request(
            self._url(table, query),
            headers=self._headers(),
            method="DELETE",
        )
        self._urlopen(req, timeout=self._config.timeout_seconds).close()

    def rpc(
        self,
        name: str,
        params: Mapping[str, Any] | None = None,
    ) -> object:
        req = urllib.request.Request(
            f"{self._config.url.rstrip('/')}/rest/v1/rpc/{name}",
            data=json.dumps(dict(params or {})).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        with self._urlopen(req, timeout=self._config.timeout_seconds) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else None
