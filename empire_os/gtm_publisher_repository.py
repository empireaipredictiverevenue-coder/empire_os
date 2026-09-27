"""Canonical persistence repository for GTM publication."""
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


class GTMPublisherRepository:
    def __init__(self, gateway: CanonicalDataGateway) -> None:
        self._gateway = gateway

    @classmethod
    def from_environment(cls) -> "GTMPublisherRepository":
        env = load_runtime_env(ENV_PATH)
        return cls(gateway_from_environment(env))

    def find_opportunity(
        self,
        niche: str,
        metro: str,
    ) -> dict[str, Any] | None:
        rows = self._gateway.query(
            "gtm_opportunities",
            "id,niche,niche_family,metro",
            filters=(
                DataFilter.eq("niche", niche),
                DataFilter.eq("metro", metro),
            ),
            limit=1,
        )
        return dict(rows[0]) if rows else None

    def update_opportunity(
        self,
        opportunity_id: str,
        payload: Mapping[str, Any],
    ) -> None:
        self._gateway.update(
            "gtm_opportunities",
            {"id": opportunity_id},
            dict(payload),
        )

    def insert_opportunity(
        self,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        rows = self._gateway.insert(
            "gtm_opportunities",
            dict(payload),
            return_repr=True,
        )
        if not rows:
            raise RuntimeError("opportunity insert returned no row")
        return dict(rows[0])

    def insert_job_if_new(
        self,
        payload: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        rows = self._gateway.insert_ignore_conflicts(
            "gtm_jobs",
            dict(payload),
            return_repr=True,
        )
        return dict(rows[0]) if rows else None

    def append_event(
        self,
        payload: Mapping[str, Any],
    ) -> None:
        self._gateway.insert(
            "commercial_events",
            dict(payload),
            return_repr=False,
        )
