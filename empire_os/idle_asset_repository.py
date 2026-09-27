"""Canonical data repository for the idle-asset sniper agent."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from empire_os.canonical_data_gateway import (
    CanonicalDataGateway,
    gateway_from_environment,
)
from empire_os.data_query import DataFilter
from empire_os.runtime_env import load_runtime_env


ENV_PATH = "/etc/empire_os.env"


class IdleAssetRepository:
    def __init__(self, gateway: CanonicalDataGateway) -> None:
        self._gateway = gateway

    @classmethod
    def from_environment(cls) -> "IdleAssetRepository":
        env = load_runtime_env(ENV_PATH)
        return cls(gateway_from_environment(env))

    def pending_review_exists(self, url: str, *, limit: int = 200) -> bool:
        rows = self._gateway.query(
            "empire_tasks",
            "id,payload",
            filters=(
                DataFilter.eq("task_type", "idle_asset_review"),
                DataFilter.eq("status", "pending"),
            ),
            limit=max(1, min(int(limit), 500)),
        )
        target = str(url or "")
        return any(
            isinstance(row.get("payload"), Mapping)
            and str(row["payload"].get("url") or "") == target
            for row in rows
        )

    def queue_review(self, row: Mapping[str, Any]) -> None:
        self._gateway.insert(
            "empire_tasks",
            dict(row),
            return_repr=False,
        )

    def enriched_candidates(self, *, limit: int = 20) -> list[dict[str, Any]]:
        return self._gateway.query(
            "idle_asset_enriched",
            "compound_id,business_name,industry,lead_gen_score",
            filters=(DataFilter.gte("lead_gen_score", 0.6),),
            limit=max(1, min(int(limit), 100)),
        )
