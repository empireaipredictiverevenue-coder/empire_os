"""Canonical read repository for identity resolution."""
from __future__ import annotations

from typing import Any

from empire_os.canonical_data_gateway import (
    CanonicalDataGateway,
    gateway_from_environment,
)
from empire_os.runtime_env import load_runtime_env


ENV_PATH = "/etc/empire_os.env"


class IdentityResolverRepository:
    def __init__(self, gateway: CanonicalDataGateway) -> None:
        self._gateway = gateway

    @classmethod
    def from_environment(cls) -> "IdentityResolverRepository":
        env = load_runtime_env(ENV_PATH)
        return cls(gateway_from_environment(env))

    @property
    def backend_name(self) -> str:
        return self._gateway.backend.value

    def fetch_prospects(
        self,
        *,
        batch_size: int = 1000,
        max_rows: int = 100000,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        bounded_batch = max(1, min(int(batch_size), 10000))
        bounded_max = max(1, int(max_rows))

        while len(rows) < bounded_max:
            page = self._gateway.query(
                "prospects",
                "id,business_name,niche,metro,phone,website,status,created_at",
                limit=min(bounded_batch, bounded_max - len(rows)),
                offset=offset,
            )
            if not page:
                break
            rows.extend(page)
            if len(page) < bounded_batch:
                break
            offset += len(page)

        return rows
