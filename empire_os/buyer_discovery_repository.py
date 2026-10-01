"""Canonical read repository for buyer discovery preview."""
from __future__ import annotations

from typing import Any

from empire_os.canonical_data_gateway import (
    CanonicalDataGateway,
    empiredb_gateway_from_environment as gateway_from_environment,
)
from empire_os.data_query import DataFilter, OrderSpec
from empire_os.runtime_env import load_runtime_env


ENV_PATH = "/etc/empire_os.env"


class BuyerDiscoveryRepository:
    def __init__(self, gateway: CanonicalDataGateway) -> None:
        self._gateway = gateway

    @classmethod
    def from_environment(cls) -> "BuyerDiscoveryRepository":
        env = load_runtime_env(ENV_PATH)
        return cls(gateway_from_environment(env))

    def _pages(
        self,
        table: str,
        columns: str,
        *,
        filters: tuple[DataFilter, ...] = (),
        order: tuple[OrderSpec, ...] = (),
        batch: int = 1000,
        max_rows: int = 50000,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        bounded_batch = max(1, min(int(batch), 10000))
        bounded_max = max(1, int(max_rows))
        while len(rows) < bounded_max:
            page = self._gateway.query(
                table,
                columns,
                filters=filters,
                order=order,
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

    def prospects(self) -> list[dict[str, Any]]:
        return self._pages(
            "prospects",
            "id,business_name,niche,metro,phone,website,buy_signal_score,status,notes,contact_name,contact_title,contact_source,contacted_status",
        )

    def active_entity_links(self) -> list[dict[str, Any]]:
        return self._pages(
            "prospect_entity_links",
            "prospect_id,entity_id,match_score,active",
            filters=(DataFilter.eq("active", True),),
        )

    def acquisitions(self) -> list[dict[str, Any]]:
        return self._pages(
            "prospect_acquisitions",
            "prospect_id,evidence,created_at",
            order=(OrderSpec("created_at", descending=True),),
        )
