"""Canonical read repository for the identity resolver."""
from __future__ import annotations

from typing import Any

from empire_os.canonical_data_gateway import CanonicalDataGateway


PROSPECT_COLUMNS = (
    "id,business_name,niche,metro,phone,website,status,created_at"
)


class IdentityResolverDataRepository:
    def __init__(self, gateway: CanonicalDataGateway) -> None:
        self._gateway = gateway

    def fetch_prospects(
        self,
        *,
        batch_size: int = 1000,
    ) -> list[dict[str, Any]]:
        batch_size = max(1, min(int(batch_size), 10000))
        rows: list[dict[str, Any]] = []
        offset = 0

        while True:
            batch = self._gateway.query(
                "prospects",
                PROSPECT_COLUMNS,
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

    def snapshot(self) -> dict[str, object]:
        backend = self._gateway.snapshot().as_dict()
        return {
            "backend": backend["primary_backend"],
            "configured": backend["configured"],
            "repository_authority": "read_only",
            "dual_write_enabled": backend["dual_write_enabled"],
            "write_fallback_enabled": backend["write_fallback_enabled"],
        }
