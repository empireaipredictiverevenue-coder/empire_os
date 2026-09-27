"""Canonical data repository for the GTM planning engine.

Read-only by design. GTM planning does not receive mutation authority.
"""
from __future__ import annotations

from typing import Any

from empire_os.canonical_data_gateway import CanonicalDataGateway


class GTMDataRepository:
    def __init__(self, gateway: CanonicalDataGateway) -> None:
        self._gateway = gateway

    def fetch_all(
        self,
        table: str,
        columns: str,
        *,
        batch_size: int = 1000,
    ) -> list[dict[str, Any]]:
        batch_size = max(1, min(int(batch_size), 10000))
        rows: list[dict[str, Any]] = []
        offset = 0

        while True:
            batch = self._gateway.select(
                table,
                columns,
                limit=batch_size,
                offset=offset,
            )
            if not batch:
                break

            rows.extend(batch)
            if len(batch) < batch_size:
                break
            offset += batch_size

        return rows

    def count(self, table: str) -> int:
        return self._gateway.count(table)

    def snapshot(self) -> dict[str, object]:
        snapshot = self._gateway.snapshot().as_dict()
        return {
            "backend": snapshot["primary_backend"],
            "configured": snapshot["configured"],
            "dual_write_enabled": snapshot["dual_write_enabled"],
            "write_fallback_enabled": snapshot["write_fallback_enabled"],
            "repository_authority": "read_only",
        }
