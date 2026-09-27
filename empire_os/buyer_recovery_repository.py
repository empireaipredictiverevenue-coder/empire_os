"""Canonical read repository for buyer-recovery seed refresh."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable, Protocol

from empire_os.canonical_data_gateway import (
    CanonicalDataGateway,
    gateway_from_environment,
)
from empire_os.data_query import DataFilter, OrderSpec
from empire_os.runtime_env import load_runtime_env


ENV_PATH = "/etc/empire_os.env"
Request = Callable[..., Any]


class BuyerRecoveryRepository(Protocol):
    def prospects_for_target(
        self,
        *,
        niche: str,
        territory: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        ...


class CanonicalBuyerRecoveryRepository:
    def __init__(self, gateway: CanonicalDataGateway) -> None:
        self._gateway = gateway

    @classmethod
    def from_environment(cls) -> "CanonicalBuyerRecoveryRepository":
        env = load_runtime_env(ENV_PATH)
        return cls(gateway_from_environment(env))

    def prospects_for_target(
        self,
        *,
        niche: str,
        territory: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        bounded = max(1, min(int(limit), 10))
        filters = [DataFilter.eq("niche", niche)]
        normalized = str(territory or "").casefold().strip()
        if normalized not in {
            "",
            "uk",
            "gb",
            "great britain",
            "united kingdom",
        }:
            metro_term = str(territory).split(",", 1)[0].strip()
            if metro_term:
                filters.append(
                    DataFilter.ilike("metro", f"*{metro_term}*")
                )

        rows = self._gateway.query(
            "prospects",
            "id,business_name,niche,website,metro,status,created_at",
            filters=tuple(filters),
            order=(OrderSpec("created_at", descending=True),),
            limit=min(100, bounded * 10),
        )
        return [
            dict(row)
            for row in rows
            if str(row.get("website") or "").strip()
        ][:bounded]


class RequestBuyerRecoveryRepository:
    """Compatibility adapter for existing injected request fakes."""

    def __init__(self, request: Request) -> None:
        self._request = request

    def prospects_for_target(
        self,
        *,
        niche: str,
        territory: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        from urllib.parse import urlencode

        params: dict[str, str] = {
            "select": (
                "id,business_name,niche,website,metro,status,created_at"
            ),
            "niche": "eq." + niche,
            "website": "not.is.null",
            "order": "created_at.desc",
            "limit": str(max(1, min(int(limit), 10))),
        }
        normalized = str(territory or "").casefold().strip()
        if normalized not in {
            "",
            "uk",
            "gb",
            "great britain",
            "united kingdom",
        }:
            metro_term = str(territory).split(",", 1)[0].strip()
            if metro_term:
                params["metro"] = f"ilike.*{metro_term}*"

        value = self._request(
            "GET",
            "/rest/v1/prospects?" + urlencode(params),
        ) or []
        if not isinstance(value, list):
            return []
        return [
            dict(row)
            for row in value
            if isinstance(row, Mapping)
        ]
