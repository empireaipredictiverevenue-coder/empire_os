"""Canonical data repository for governed market-pricing persistence.

Business pricing logic depends on semantic repository operations. Legacy
PostgREST request-shape compatibility lives here only for migration tests and
callers; vendor transport must not leak back into market_pricing.py.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Callable, Protocol

from empire_os.canonical_data_gateway import (
    CanonicalDataGateway,
    gateway_from_environment,
)
from empire_os.runtime_env import load_runtime_env


ENV_PATH = "/etc/empire_os.env"
Request = Callable[..., Any]


class PricingRepository(Protocol):
    def catalog_rows(
        self,
        product_code: str,
        *,
        limit: int = 1,
    ) -> list[dict[str, Any]]:
        ...

    def register_product_identity(
        self,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        ...

    def propose_product_version(
        self,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        ...


def _rows(value: object) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        return [dict(value)]
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        return [
            dict(item)
            for item in value
            if isinstance(item, Mapping)
        ]
    raise TypeError("market pricing catalog RPC returned unsupported value")


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
    raise TypeError(f"{operation} RPC returned unsupported value")


class MarketPricingRepository:
    """Backend-neutral repository for commercial pricing RPCs."""

    def __init__(self, gateway: CanonicalDataGateway) -> None:
        self._gateway = gateway

    @classmethod
    def from_environment(cls) -> "MarketPricingRepository":
        env = load_runtime_env(ENV_PATH)
        return cls(gateway_from_environment(env))

    def catalog_rows(
        self,
        product_code: str,
        *,
        limit: int = 1,
    ) -> list[dict[str, Any]]:
        value = self._gateway.rpc(
            "get_commercial_product_catalog",
            {
                "p_product_code": product_code,
                "p_limit": int(limit),
            },
        )
        return _rows(value)

    def register_product_identity(
        self,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        return _mapping(
            self._gateway.rpc(
                "register_commercial_product_identity",
                dict(payload),
            ),
            operation="register_commercial_product_identity",
        )

    def propose_product_version(
        self,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        return _mapping(
            self._gateway.rpc(
                "propose_commercial_product_version",
                dict(payload),
            ),
            operation="propose_commercial_product_version",
        )


class RequestMarketPricingRepository:
    """Compatibility adapter for existing injected request fakes/callers."""

    def __init__(self, request: Request) -> None:
        self._request = request

    def catalog_rows(
        self,
        product_code: str,
        *,
        limit: int = 1,
    ) -> list[dict[str, Any]]:
        return _rows(
            self._request(
                "POST",
                "/rest/v1/rpc/get_commercial_product_catalog",
                payload={
                    "p_product_code": product_code,
                    "p_limit": int(limit),
                },
            )
        )

    def register_product_identity(
        self,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        return _mapping(
            self._request(
                "POST",
                "/rest/v1/rpc/register_commercial_product_identity",
                payload=dict(payload),
            ),
            operation="register_commercial_product_identity",
        )

    def propose_product_version(
        self,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        return _mapping(
            self._request(
                "POST",
                "/rest/v1/rpc/propose_commercial_product_version",
                payload=dict(payload),
            ),
            operation="propose_commercial_product_version",
        )
