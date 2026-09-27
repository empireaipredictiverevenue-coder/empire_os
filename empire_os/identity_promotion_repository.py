"""Canonical persistence repository for identity promotion."""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from empire_os.canonical_data_gateway import (
    CanonicalDataGateway,
    gateway_from_environment,
)
from empire_os.data_query import DataFilter
from empire_os.runtime_env import load_runtime_env


ENV_PATH = "/etc/empire_os.env"


class IdentityPromotionRepository:
    def __init__(self, gateway: CanonicalDataGateway) -> None:
        self._gateway = gateway

    @classmethod
    def from_environment(cls) -> "IdentityPromotionRepository":
        env = load_runtime_env(ENV_PATH)
        return cls(gateway_from_environment(env))

    def existing_links(
        self,
        prospect_ids: Iterable[str],
        *,
        batch_size: int = 200,
    ) -> dict[str, str]:
        ids = [str(value) for value in prospect_ids if str(value)]
        existing: dict[str, str] = {}
        bounded = max(1, min(int(batch_size), 1000))
        for i in range(0, len(ids), bounded):
            batch = tuple(ids[i:i + bounded])
            rows = self._gateway.query(
                "prospect_entity_links",
                "prospect_id,entity_id",
                filters=(DataFilter.in_("prospect_id", batch),),
                limit=len(batch),
            )
            for row in rows:
                prospect_id = str(row.get("prospect_id") or "")
                entity_id = str(row.get("entity_id") or "")
                if prospect_id and entity_id:
                    existing[prospect_id] = entity_id
        return existing

    def ensure_entity(self, row: Mapping[str, Any]) -> None:
        self._gateway.insert_ignore_conflicts(
            "business_entities",
            dict(row),
            conflict_columns=("id",),
            return_repr=False,
        )

    def ensure_link(self, row: Mapping[str, Any]) -> None:
        self._gateway.insert_ignore_conflicts(
            "prospect_entity_links",
            dict(row),
            conflict_columns=("prospect_id",),
            return_repr=False,
        )
