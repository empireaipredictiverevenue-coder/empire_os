"""Canonical Solar Opportunity Map product identity + price proposal.

Founder-approved offer price is £249 per map. This worker may synchronize the
product identity and propose that observed/approved price into the governed
catalog. It deliberately leaves acquisition cost, fulfilment cost and margin
policy UNKNOWN, so binding commercial terms remain fail-closed.

No catalog verification, buyer approval, outbound, payment mutation or revenue
recognition occurs here.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping

from empire_os.qualification_worker_v2 import request_json


Request = Callable[..., Any]
PRODUCT_CODE = "solar_opportunity_map"
PRICE_CENTS = 24900
CURRENCY = "GBP"


def _catalog_rows(request: Request) -> list[dict[str, Any]]:
    rows = request(
        "POST",
        "/rest/v1/rpc/get_commercial_product_catalog",
        payload={
            "p_product_code": PRODUCT_CODE,
            "p_limit": 1,
        },
    ) or []
    if isinstance(rows, Mapping):
        rows = [rows]
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _price_matches(row: Mapping[str, Any]) -> bool:
    basis = row.get("price_basis")
    if not isinstance(basis, Mapping):
        return False
    try:
        amount = int(basis.get("amount_cents"))
    except (TypeError, ValueError):
        return False
    return (
        str(basis.get("state") or "").upper() == "VERIFIED"
        and str(basis.get("currency") or "").upper() == CURRENCY
        and amount == PRICE_CENTS
        and str(basis.get("unit") or "") == "per_map"
        and str(row.get("billing_model") or "") == "one_time"
        and str(row.get("version_state") or "").upper()
        in {"PENDING", "VERIFIED"}
    )


def sync_solar_opportunity_map_product(
    request: Request = request_json,
) -> dict[str, Any]:
    rows = _catalog_rows(request)
    if rows and _price_matches(rows[0]):
        return {
            "schema_version": "empire.solar-product-sync.v1",
            "product_code": PRODUCT_CODE,
            "identity": {
                "decision": "existing",
                "product_id": rows[0].get("product_id"),
            },
            "price_version": {
                "decision": "existing",
                "version_id": rows[0].get("version_id"),
                "version": rows[0].get("version"),
                "version_state": rows[0].get("version_state"),
            },
            "price_cents": PRICE_CENTS,
            "currency": CURRENCY,
            "binding_terms_ready": bool(
                rows[0].get("binding_terms_ready") is True
            ),
            "economics_complete": False,
            "catalog_verification_attempted": False,
            "outbound_sent": False,
            "payment_mutation": False,
            "recognized_revenue": False,
            "actual_revenue": False,
        }

    identity = request(
        "POST",
        "/rest/v1/rpc/register_commercial_product_identity",
        payload={
            "p_product_code": PRODUCT_CODE,
            "p_product_name": "Solar Opportunity Map",
            "p_product_family": "search_intelligence",
            "p_billing_model": "one_time",
            "p_configuration": {
                "niche": "solar",
                "delivery": "evidence_backed_opportunity_map",
                "artifact_schema": "empire.solar-opportunity-map.v2",
                "execution_authority": "internal_artifact_only",
            },
            "p_provenance": {
                "source": "empire_os.solar_opportunity_map",
                "pricing_observed": True,
                "price_approval": "founder_approved",
                "economics_state": "PARTIAL",
            },
            "p_actor": "solar-opportunity-map-product-sync",
        },
    ) or {}


    proposed = request(
        "POST",
        "/rest/v1/rpc/propose_commercial_product_version",
        payload={
            "p_product_code": PRODUCT_CODE,
            "p_billing_model": "one_time",
            "p_currency": CURRENCY,
            "p_price_basis": {
                "state": "VERIFIED",
                "amount_cents": PRICE_CENTS,
                "currency": CURRENCY,
                "unit": "per_map",
                "billing_model": "one_time",
                "source_type": "founder_approved",
                "basis": "founder_agreed_solar_opportunity_map_offer",
            },
            "p_acquisition_cost_basis": {
                "state": "UNKNOWN",
                "reason": "actual_acquisition_cost_not_yet_verified",
            },
            "p_fulfilment_cost_basis": {
                "state": "UNKNOWN",
                "reason": "actual_fulfilment_cost_not_yet_verified",
            },
            "p_margin_policy": {
                "state": "UNKNOWN",
                "reason": "founder_margin_policy_not_yet_bound",
            },
            "p_provenance": {
                "source": "empire_os.solar_opportunity_map",
                "price_source_type": "founder_approved",
                "binding_terms_ready": False,
            },
            "p_evidence_refs": [
                "founder_approved_offer:solar_opportunity_map:GBP249",
            ],
            "p_effective_from": None,
            "p_effective_until": None,
            "p_actor": "solar-opportunity-map-product-sync",
        },
    ) or {}

    return {
        "schema_version": "empire.solar-product-sync.v1",
        "product_code": PRODUCT_CODE,
        "identity": identity,
        "price_version": proposed,
        "price_cents": PRICE_CENTS,
        "currency": CURRENCY,
        "binding_terms_ready": False,
        "economics_complete": False,
        "catalog_verification_attempted": False,
        "outbound_sent": False,
        "payment_mutation": False,
        "recognized_revenue": False,
        "actual_revenue": False,
    }
