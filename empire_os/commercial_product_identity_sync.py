"""Synchronize known sellable product identities into the commercial catalog.

This worker never supplies price, cost or margin values. Catalog economics stay
UNKNOWN until a separate evidence-backed version is proposed and verified.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping

from empire_os.search_intelligence.products import SEARCH_PRODUCTS
from empire_os.commercial_recovery_registry import RECOVERY_PRODUCTS


Request = Callable[..., Any]


def search_product_identity_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for product in SEARCH_PRODUCTS:
        rows.append({
            "product_code": product.key,
            "product_name": product.name,
            "product_family": "search_intelligence",
            "billing_model": product.commercial_model,
            "configuration": {
                "category": product.category,
                "outcome": product.outcome,
                "buyer_types": list(product.buyer_types),
                "deliverables": list(product.deliverables),
                "required_capabilities": list(
                    product.required_capabilities
                ),
                "optional_capabilities": list(
                    product.optional_capabilities
                ),
                "revenue_models": list(product.revenue_models),
                "execution_mode": product.execution_mode,
            },
            "provenance": {
                "source": "empire_os.search_intelligence.products",
                "pricing_observed": False,
                "economics_state": "UNKNOWN",
            },
        })
    return rows


def strategic_product_identity_rows() -> list[dict[str, Any]]:
    promoted_codes = {
        "permit_intelligence",
        "property_intelligence",
        "private_capital_rollup",
    }
    rows: list[dict[str, Any]] = []
    for product in RECOVERY_PRODUCTS:
        if product.key not in promoted_codes:
            continue
        rows.append({
            "product_code": product.key,
            "product_name": product.name,
            "product_family": product.family,
            "billing_model": "terms_required",
            "configuration": {
                "recovery_state": product.state,
                "revenue_models": list(product.revenue_models),
                "surfaces": list(product.surfaces),
                "execution_authority": product.execution_authority,
            },
            "provenance": {
                "source": "empire_os.commercial_recovery_registry",
                "pricing_observed": False,
                "economics_state": "UNKNOWN",
            },
        })
    return rows


def sync_commercial_product_identities(
    request: Request,
) -> dict[str, Any]:
    rows = [
        *search_product_identity_rows(),
        *strategic_product_identity_rows(),
    ]
    synchronized = 0
    errors: list[str] = []

    for row in rows:
        try:
            result = request(
                "POST",
                "/rest/v1/rpc/register_commercial_product_identity",
                payload={
                    "p_product_code": row["product_code"],
                    "p_product_name": row["product_name"],
                    "p_product_family": row["product_family"],
                    "p_billing_model": row["billing_model"],
                    "p_configuration": row["configuration"],
                    "p_provenance": row["provenance"],
                    "p_actor": "commercial-product-identity-sync",
                },
            ) or {}
            if isinstance(result, Mapping) and result.get("product_id"):
                synchronized += 1
            else:
                errors.append(
                    f"{row['product_code']}:identity_sync_no_product_id"
                )
        except Exception as exc:
            errors.append(
                f"{row['product_code']}:{type(exc).__name__}:"
                f"{str(exc)[:180]}"
            )

    return {
        "schema_version": "empire.commercial-product-identity-sync.v1",
        "known_products": len(rows),
        "synchronized": synchronized,
        "errors": errors,
        "pricing_observed": False,
        "economics_mutated": False,
        "terms_approved": False,
        "payment_mutation": False,
        "actual_revenue": False,
        "ok": not errors,
    }
