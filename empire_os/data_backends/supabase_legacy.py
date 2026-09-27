"""Legacy Supabase provider behind the Canonical Data Gateway.

This adapter exists only for migration compatibility. New EmpireOS business
logic should depend on CanonicalDataGateway, not on this module.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping, Sequence
import urllib.parse
import urllib.request

from empire_os.data_cloud_contract import DataBackend


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
