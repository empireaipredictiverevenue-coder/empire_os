"""Apply founder-approved Solar Opportunity Map economics.

This worker proposes a complete founder-approved product version and invokes the
existing deterministic catalog verifier. It does not send outreach, create
payment requests, move funds, or recognize revenue.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping

from empire_os.market_pricing import SOLAR_OPPORTUNITY_MAP_PRICES
from empire_os.qualification_worker_v2 import request_json
from empire_os.solar_economics_policy import catalog_economics_basis


Request = Callable[..., Any]


def _catalog_rows(
    request: Request,
    product_code: str,
) -> list[dict[str, Any]]:
    rows = request(
        "POST",
        "/rest/v1/rpc/get_commercial_product_catalog",
        payload={
            "p_product_code": product_code,
            "p_limit": 1,
        },
    ) or []
    if isinstance(rows, Mapping):
        rows = [rows]
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _already_verified(row: Mapping[str, Any]) -> bool:
    return (
        str(row.get("version_state") or "").upper() == "VERIFIED"
        and str(row.get("catalog_state") or "").upper() == "VERIFIED"
        and row.get("binding_terms_ready") is True
    )


def apply_market_economics(
    country_code: str,
    *,
    request: Request = request_json,
) -> dict[str, Any]:
    basis = catalog_economics_basis(country_code)
    existing = _catalog_rows(request, basis["product_code"])
    if existing and _already_verified(existing[0]):
        return {
            "country_code": country_code,
            "product_code": basis["product_code"],
            "decision": "existing_verified",
            "version_id": existing[0].get("version_id"),
            "binding_terms_ready": True,
            "outbound_sent": False,
            "payment_mutation": False,
            "recognized_revenue": False,
            "actual_revenue": False,
        }

    proposed = request(
        "POST",
        "/rest/v1/rpc/propose_commercial_product_version",
        payload={
            "p_product_code": basis["product_code"],
            "p_billing_model": basis["billing_model"],
            "p_currency": basis["currency"],
            "p_price_basis": basis["price_basis"],
            "p_acquisition_cost_basis": basis["acquisition_cost_basis"],
            "p_fulfilment_cost_basis": basis["fulfilment_cost_basis"],
            "p_margin_policy": basis["margin_policy"],
            "p_provenance": basis["provenance"],
            "p_evidence_refs": basis["evidence_refs"],
            "p_effective_from": None,
            "p_effective_until": None,
            "p_actor": "founder-approved-solar-economics",
        },
    ) or {}
    version_id = str(proposed.get("version_id") or "").strip()
    if not version_id:
        raise RuntimeError("catalog proposal returned no version_id")

    verified = request(
        "POST",
        "/rest/v1/rpc/auto_verify_commercial_product_version",
        payload={"p_version_id": version_id},
    ) or {}

    return {
        "country_code": country_code,
        "product_code": basis["product_code"],
        "decision": verified.get("decision") or "unknown",
        "version_id": version_id,
        "proposal": proposed,
        "verification": verified,
        "binding_terms_ready": (
            str(verified.get("decision") or "").lower() == "verified"
        ),
        "outbound_sent": False,
        "payment_mutation": False,
        "recognized_revenue": False,
        "actual_revenue": False,
    }


def apply_all_solar_economics(
    request: Request = request_json,
) -> dict[str, Any]:
    results = []
    errors = []
    for country_code in SOLAR_OPPORTUNITY_MAP_PRICES:
        try:
            results.append(
                apply_market_economics(
                    country_code,
                    request=request,
                )
            )
        except Exception as exc:
            errors.append({
                "country_code": country_code,
                "error": f"{type(exc).__name__}:{str(exc)[:260]}",
            })

    verified_count = sum(
        bool(row.get("binding_terms_ready"))
        for row in results
    )
    return {
        "schema_version": "empire.solar-economics-apply.v1",
        "attempted": len(SOLAR_OPPORTUNITY_MAP_PRICES),
        "verified_count": verified_count,
        "error_count": len(errors),
        "results": results,
        "errors": errors,
        "outbound_sent": False,
        "payment_mutation": False,
        "recognized_revenue": False,
        "actual_revenue": False,
        "execution_authority": "catalog_economics_only",
    }
