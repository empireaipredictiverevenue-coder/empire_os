"""Owner-controlled mount factory for the EXISTING authenticated EmpireOS gateway.

Reuse first-party Search Fabric direct public fetching when explicitly selected.
No independent service, implicit paid provider, DB migration or billing.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from fastapi import FastAPI

from .durable_api import create_metered_private_app
from .empiredb_metering_adapter import EmpireDbMeteringStore

FIRST_PARTY_SEARCH_SOURCE = "empire_search_fabric_public"


def _first_party_search_adapter(
    direct_public_fetch: Callable[..., list[dict[str, Any]]],
    quality_filter: Callable[[list[dict[str, Any]], str, int], list[dict[str, Any]]],
) -> Callable[[str, int], Mapping[str, Any]]:
    """Adapt an actual, non-cached Search Fabric public fetch to the original API.

    The owner must pass Search Fabric's public_fallback.search_public_web or
    another directly observed, equivalent source. Do not use search_reliable:
    its cache and optional paid Decodo path are not a direct fresh observation.
    """
    if not callable(direct_public_fetch):
        raise ValueError("existing_first_party_public_fetch_required")
    if not callable(quality_filter):
        raise ValueError("existing_search_fabric_quality_filter_required")

    def run(query: str, limit: int) -> Mapping[str, Any]:
        if type(query) is not str or not 3 <= len(query) <= 180:
            raise ValueError("invalid_first_party_search_query")
        if type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError("invalid_first_party_search_limit")
        rows = direct_public_fetch(query, num=limit)
        # PublicSearchRows is a list subclass with evidence of a genuinely
        # responsive search engine, including confirmed empty SERPs.
        if not isinstance(rows, list) or getattr(rows, "provider_available", None) is not True:
            raise ValueError("first_party_public_search_unavailable")
        # Reuse Search Fabric's EXISTING relevance scoring. A responsive
        # provider can yield unrelated rows; never sell those as good matches.
        qualified = quality_filter(rows, query, limit)
        if not isinstance(qualified, list) or len(qualified) > limit:
            raise ValueError("existing_search_fabric_quality_filter_invalid")
        safe_rows = []
        for row in qualified:
            if type(row) is not dict:
                raise ValueError("first_party_search_row_invalid")
            if type(row.get("engine")) is not str or row["engine"] not in {
                "bing_html", "duckduckgo_html", "brave_web", "google_html",
            }:
                raise ValueError("first_party_search_underlying_engine_unknown")
            safe_rows.append(row)
        return {
            "source_id": FIRST_PARTY_SEARCH_SOURCE,
            "source_observed_at": datetime.now(timezone.utc).isoformat(),
            "search_operational_status": "HEALTHY",
            "searchParameters": {
                "search_state": "RESULTS" if safe_rows else "NO_RELEVANT_RESULTS",
                "engine": FIRST_PARTY_SEARCH_SOURCE,
                "cache": False,
            },
            "organic": safe_rows,
        }

    return run


def create_gateway_candidate_app(
    *,
    connect_factory: Callable[[], Any],
    site_adapter: Callable[[str], Mapping[str, Any]] | None = None,
    site_adapter_egress_reviewed: bool = False,
    enable_first_party_search: bool = False,
    first_party_public_fetch: Callable[..., list[dict[str, Any]]] | None = None,
    first_party_quality_filter: Callable[
        [list[dict[str, Any]], str, int], list[dict[str, Any]]
    ] | None = None,
    # Existing owner-supplied access/usage checks for our own collector:
    # NO third-party supplier contract is a universal prerequisite.
    source_request_preflight: Callable[[str, str, str, int], bool] | None = None,
    source_output_check: Callable[[str, str, Mapping[str, Any]], bool] | None = None,
) -> FastAPI:
    """Original API, authenticated tenant/host gateway, explicit source policy.

    Defaults continue to expose founder usage only. The original route owner
    separately controls actual mounting and metering rights; this function
    does not grant production network, keys, or database authority.
    """
    adapter = None
    if enable_first_party_search:
        if not callable(source_request_preflight) or not callable(source_output_check):
            raise ValueError("first_party_source_use_policy_callbacks_required")
        if first_party_public_fetch is None:
            # Lazy import only on explicit activation; use the EXISTING engine.
            from empire_os.search_fabric.public_fallback import search_public_web
            first_party_public_fetch = search_public_web
        if first_party_quality_filter is None:
            from empire_os.search_fabric.search import _quality_filter
            first_party_quality_filter = _quality_filter
        adapter = _first_party_search_adapter(
            first_party_public_fetch, first_party_quality_filter,
        )
    return create_metered_private_app(
        store=EmpireDbMeteringStore(connect_factory),
        search_adapter=adapter,
        search_source_id=FIRST_PARTY_SEARCH_SOURCE if adapter is not None else None,
        licensed_search_output=adapter is not None,
        # Only this exact first-party direct public HTML adapter uses a
        # verifiable zero *paid search API* fee; infrastructure cost is NOT 0.
        first_party_direct_public_no_paid_fee=adapter is not None,
        source_rights_check=source_output_check if adapter is not None else None,
        source_request_preflight=source_request_preflight if adapter is not None else None,
        site_adapter=site_adapter,
        site_adapter_egress_reviewed=site_adapter_egress_reviewed,
        require_gateway_attestation=True,
    )
