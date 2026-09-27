"""Canonical repository for GTM standing-authority review and intent data.

The business bridge owns review policy and copy decisions. This repository owns
data access semantics and keeps legacy request-shape compatibility outside the
business module during Empire Data Cloud migration.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Callable, Protocol
import urllib.parse

from empire_os.canonical_data_gateway import (
    CanonicalDataGateway,
    gateway_from_environment,
)
from empire_os.data_query import DataFilter, OrderSpec
from empire_os.runtime_env import load_runtime_env


ENV_PATH = "/etc/empire_os.env"
Request = Callable[..., Any]


class StandingBridgeRepository(Protocol):
    def pending_reviews(self, *, limit: int) -> list[dict[str, Any]]:
        ...

    def auto_review(
        self,
        review_id: str,
        *,
        daily_cap: int,
    ) -> dict[str, Any]:
        ...

    def approved_for_outbound(self, *, limit: int) -> list[dict[str, Any]]:
        ...

    def propose_outbound_intent(
        self,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        ...


def _rows(value: object) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        nested = value.get("result") or value.get("reviews")
        if nested is not None:
            value = nested
        else:
            return [dict(value)]
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        return [
            dict(item)
            for item in value
            if isinstance(item, Mapping)
        ]
    raise TypeError("standing bridge data source returned unsupported value")


def _mapping(value: object, *, operation: str) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if (
        isinstance(value, Sequence)
        and not isinstance(value, (str, bytes, bytearray))
        and len(value) == 1
        and isinstance(value[0], Mapping)
    ):
        return dict(value[0])
    raise TypeError(f"{operation} returned unsupported value")


class CanonicalStandingBridgeRepository:
    def __init__(self, gateway: CanonicalDataGateway) -> None:
        self._gateway = gateway

    @classmethod
    def from_environment(cls) -> "CanonicalStandingBridgeRepository":
        env = load_runtime_env(ENV_PATH)
        return cls(gateway_from_environment(env))

    def pending_reviews(self, *, limit: int) -> list[dict[str, Any]]:
        bounded = max(1, min(int(limit), 50))
        return self._gateway.query(
            "buyer_candidate_reviews",
            "id,status,offer_key,proposed_at,evidence",
            filters=(
                DataFilter.eq("status", "pending"),
                DataFilter.eq("offer_key", "managed_service"),
            ),
            order=(OrderSpec("proposed_at"),),
            limit=bounded,
        )

    def auto_review(
        self,
        review_id: str,
        *,
        daily_cap: int,
    ) -> dict[str, Any]:
        return _mapping(
            self._gateway.rpc(
                "auto_review_buyer_candidate",
                {
                    "p_review_id": review_id,
                    "p_daily_cap": max(1, min(int(daily_cap), 50)),
                },
            ),
            operation="auto_review_buyer_candidate",
        )

    def approved_for_outbound(self, *, limit: int) -> list[dict[str, Any]]:
        return _rows(
            self._gateway.rpc(
                "list_buyer_reviews_for_outbound",
                {"p_limit": max(1, min(int(limit), 50))},
            )
        )

    def propose_outbound_intent(
        self,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        return _mapping(
            self._gateway.rpc(
                "propose_reviewed_outbound_intent",
                dict(payload),
            ),
            operation="propose_reviewed_outbound_intent",
        )


class RequestStandingBridgeRepository:
    """Compatibility adapter for existing injected legacy request callables."""

    def __init__(self, request: Request) -> None:
        self._request = request

    def pending_reviews(self, *, limit: int) -> list[dict[str, Any]]:
        bounded = max(1, min(int(limit), 50))
        params = urllib.parse.urlencode({
            "select": "id,status,offer_key,proposed_at,evidence",
            "status": "eq.pending",
            "offer_key": "eq.managed_service",
            "order": "proposed_at.asc",
            "limit": bounded,
        })
        return _rows(
            self._request(
                "GET",
                f"/rest/v1/buyer_candidate_reviews?{params}",
            )
        )

    def auto_review(
        self,
        review_id: str,
        *,
        daily_cap: int,
    ) -> dict[str, Any]:
        return _mapping(
            self._request(
                "POST",
                "/rest/v1/rpc/auto_review_buyer_candidate",
                payload={
                    "p_review_id": review_id,
                    "p_daily_cap": max(1, min(int(daily_cap), 50)),
                },
            ),
            operation="auto_review_buyer_candidate",
        )

    def approved_for_outbound(self, *, limit: int) -> list[dict[str, Any]]:
        return _rows(
            self._request(
                "POST",
                "/rest/v1/rpc/list_buyer_reviews_for_outbound",
                payload={"p_limit": max(1, min(int(limit), 50))},
            )
        )

    def propose_outbound_intent(
        self,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        return _mapping(
            self._request(
                "POST",
                "/rest/v1/rpc/propose_reviewed_outbound_intent",
                payload=dict(payload),
            ),
            operation="propose_reviewed_outbound_intent",
        )
