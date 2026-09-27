"""Canonical data repository for the Idle Asset Sniper.

The agent remains FIND/REVIEW only. This repository can read enriched candidates
and write human-review tasks, but has no outreach or fulfilment authority.
"""
from __future__ import annotations

from typing import Any

from empire_os.canonical_data_gateway import CanonicalDataGateway
from empire_os.data_query import DataFilter


class IdleAssetDataRepository:
    def __init__(self, gateway: CanonicalDataGateway) -> None:
        self._gateway = gateway

    @property
    def configured(self) -> bool:
        return self._gateway.configured

    def pending_review_urls(self) -> set[str]:
        rows = self._gateway.query(
            "empire_tasks",
            "payload",
            filters=(
                DataFilter.eq("task_type", "idle_asset_review"),
                DataFilter.eq("status", "pending"),
            ),
            limit=5000,
        )
        return {
            str(payload.get("url") or "").strip()
            for row in rows
            if isinstance(row, dict)
            and isinstance((payload := row.get("payload")), dict)
            and str(payload.get("url") or "").strip()
        }

    def enriched_candidates(
        self,
        *,
        minimum_score: float = 0.6,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        return self._gateway.query(
            "idle_asset_enriched",
            "compound_id,business_name,industry,lead_gen_score",
            filters=(DataFilter.gte("lead_gen_score", minimum_score),),
            limit=max(1, min(int(limit), 1000)),
        )

    def queue_review(self, row: dict[str, Any]) -> None:
        self._gateway.insert(
            "empire_tasks",
            row,
            return_repr=False,
        )

    def snapshot(self) -> dict[str, object]:
        backend = self._gateway.snapshot().as_dict()
        return {
            "backend": backend["primary_backend"],
            "configured": backend["configured"],
            "repository_authority": "idle_asset_review_only",
            "outreach_authority": False,
            "dual_write_enabled": backend["dual_write_enabled"],
            "write_fallback_enabled": backend["write_fallback_enabled"],
        }
