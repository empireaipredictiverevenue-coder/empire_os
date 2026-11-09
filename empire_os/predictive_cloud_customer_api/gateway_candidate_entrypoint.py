"""Owner-controlled mount factory for a future authenticated EmpireOS gateway.

Do not run as an independent service. The host gateway owner must own mounting,
first-party identity attestation and network policy. No default provider calls,
DB migrations, billing or outbound authority are conferred by this factory.
"""
from __future__ import annotations
from typing import Any, Callable, Mapping
from fastapi import FastAPI
from .durable_api import create_metered_private_app
from .empiredb_metering_adapter import EmpireDbMeteringStore


def create_gateway_candidate_app(
    *,
    connect_factory: Callable[[], Any],
    site_adapter: Callable[[str], Mapping[str, Any]] | None = None,
    site_adapter_egress_reviewed: bool = False,
) -> FastAPI:
    """Requires trusted ASGI principal + separate API key for all routes.

    No customer search adapter is mounted by default: the existing self-hosted
    Search Fabric route needs owner-approved source-use and egress controls,
    not a mandatory third-party supplier contract. Site audit requires
    separately reviewed connect-time egress.
    """
    return create_metered_private_app(
        store=EmpireDbMeteringStore(connect_factory),
        search_adapter=None,
        site_adapter=site_adapter,
        licensed_search_output=False,
        source_rights_check=None,
        site_adapter_egress_reviewed=site_adapter_egress_reviewed,
        require_gateway_attestation=True,
    )
