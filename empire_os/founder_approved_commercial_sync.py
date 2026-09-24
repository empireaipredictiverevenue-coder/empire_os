"""Idempotent sync for founder-approved Exchange and Predictive Revenue pricing.

This persists product identity + approved price into the canonical commercial
catalog. It intentionally leaves acquisition cost, fulfilment cost and margin
UNKNOWN until separately verified. Therefore it does not auto-verify a catalog
version, activate a seat, request payment or recognize revenue.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping

from empire_os.phase4_exchange_mrr_products import EXCHANGE_MRR_PRODUCTS
from empire_os.predictive_revenue_products import PREDICTIVE_REVENUE_PRODUCTS
from empire_os.qualification_worker_v2 import request_json


Request = Callable[..., Any]


def _identity_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for item in EXCHANGE_MRR_PRODUCTS:
        rows.append({
            "product_code": item.product_code,
            "product_name": item.name,
            "product_family": "commercial_exchange",
            "billing_model": "usage_and_subscription",
            "currency": "USD",
            "amount_cents": item.monthly_price_cents,
            "unit": "per_month",
            "configuration": {
                "currency": "USD",
                "corridor_limit": item.corridor_limit,
                "monthly_price_cents": item.monthly_price_cents,
                "usage_discount_bps": item.usage_discount_bps,
                "pricing_state": item.pricing_state,
                "price_approved_at": item.price_approved_at,
                "lead_classes": list(item.lead_classes),
                "allocation_priority": item.allocation_priority,
                "territory_model": item.territory_model,
                "settlement": "USDT_BSC",
            },
            "evidence_ref": (
                "founder_approval:2026-09-24:"
                "lead_exchange_launch_pricing"
            ),
            "source": "empire_os.phase4_exchange_mrr_products",
        })

    for item in PREDICTIVE_REVENUE_PRODUCTS:
        rows.append({
            "product_code": item.product_code,
            "product_name": item.name,
            "product_family": "predictive_revenue",
            "billing_model": item.billing_model,
            "currency": item.currency,
            "amount_cents": item.deployment_price_cents,
            "unit": "per_deployment",
            "configuration": {
                "currency": item.currency,
                "deployment_price_cents": item.deployment_price_cents,
                "price_type": item.price_type,
                "pricing_state": item.pricing_state,
                "price_approved_at": item.price_approved_at,
                "execution_mode": item.execution_mode,
                "settlement": "USDT_BSC",
            },
            "evidence_ref": (
                "founder_approval:2026-09-24:"
                "predictive_revenue_enterprise_pricing"
            ),
            "source": "empire_os.predictive_revenue_products",
        })

    return rows


def _catalog_row(
    request: Request,
    product_code: str,
) -> dict[str, Any] | None:
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
    if not isinstance(rows, list) or not rows:
        return None
    row = rows[0]
    return dict(row) if isinstance(row, Mapping) else None


def _matching_price(row: Mapping[str, Any] | None, expected: Mapping[str, Any]) -> bool:
    if not row:
        return False
    price = row.get("price_basis")
    if not isinstance(price, Mapping):
        return False
    try:
        amount = int(price.get("amount_cents"))
    except (TypeError, ValueError):
        return False
    return (
        str(price.get("state") or "").upper() == "VERIFIED"
        and str(price.get("source_type") or "") == "founder_approved"
        and str(price.get("currency") or "").upper() == expected["currency"]
        and amount == int(expected["amount_cents"])
        and str(price.get("unit") or "") == expected["unit"]
    )


def sync_founder_approved_commercial_pricing(
    request: Request = request_json,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for row in _identity_rows():
        code = row["product_code"]
        try:
            identity = request(
                "POST",
                "/rest/v1/rpc/register_commercial_product_identity",
                payload={
                    "p_product_code": code,
                    "p_product_name": row["product_name"],
                    "p_product_family": row["product_family"],
                    "p_billing_model": row["billing_model"],
                    "p_configuration": row["configuration"],
                    "p_provenance": {
                        "source": row["source"],
                        "founder_approved": True,
                        "approved_at": "2026-09-24",
                        "actual_revenue": False,
                    },
                    "p_actor": "founder-approved-commercial-sync",
                },
            ) or {}

            existing = _catalog_row(request, code)
            if _matching_price(existing, row):
                results.append({
                    "product_code": code,
                    "decision": "existing_approved_price",
                    "product_id": identity.get("product_id")
                    if isinstance(identity, Mapping) else None,
                    "version_id": existing.get("version_id")
                    if existing else None,
                    "binding_terms_ready": bool(
                        existing.get("binding_terms_ready")
                    ) if existing else False,
                    "actual_revenue": False,
                })
                continue

            proposed = request(
                "POST",
                "/rest/v1/rpc/propose_commercial_product_version",
                payload={
                    "p_product_code": code,
                    "p_billing_model": row["billing_model"],
                    "p_currency": row["currency"],
                    "p_price_basis": {
                        "state": "VERIFIED",
                        "source_type": "founder_approved",
                        "currency": row["currency"],
                        "amount_cents": row["amount_cents"],
                        "unit": row["unit"],
                        "approved_at": "2026-09-24",
                    },
                    "p_acquisition_cost_basis": {
                        "state": "UNKNOWN",
                        "observed_cost_claim": False,
                    },
                    "p_fulfilment_cost_basis": {
                        "state": "UNKNOWN",
                        "observed_cost_claim": False,
                    },
                    "p_margin_policy": {"state": "UNKNOWN"},
                    "p_provenance": {
                        "source": "founder_approved_commercial_sync",
                        "price_approved_at": "2026-09-24",
                        "binding_terms_ready": False,
                        "actual_revenue": False,
                    },
                    "p_evidence_refs": [row["evidence_ref"]],
                    "p_effective_from": None,
                    "p_effective_until": None,
                    "p_actor": "founder-approved-commercial-sync",
                },
            ) or {}

            results.append({
                "product_code": code,
                "decision": "approved_price_proposed",
                "product_id": identity.get("product_id")
                if isinstance(identity, Mapping) else None,
                "version_id": proposed.get("version_id")
                if isinstance(proposed, Mapping) else None,
                "binding_terms_ready": False,
                "actual_revenue": False,
            })
        except Exception as exc:
            errors.append({
                "product_code": code,
                "error": f"{type(exc).__name__}:{str(exc)[:240]}",
            })

    return {
        "schema_version": "empire.founder-approved-commercial-sync.v1",
        "attempted": len(_identity_rows()),
        "result_count": len(results),
        "error_count": len(errors),
        "results": results,
        "errors": errors,
        "price_authority": "founder_approved_2026_09_24",
        "costs_verified": False,
        "binding_terms_mutated": False,
        "payment_mutation": False,
        "actual_revenue": False,
        "ok": not errors,
    }
