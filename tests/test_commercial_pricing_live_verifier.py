from datetime import datetime, timezone

from empire_os.commercial_pricing_live_verifier import (
    verify_catalog_snapshot,
)
from empire_os.commercial_pricing_policy import LAUNCH_PRICING


def snapshot():
    products = []
    for policy in LAUNCH_PRICING:
        products.append({
            "product_code": policy.product_code,
            "catalog_state": "VERIFIED",
            "version_state": "VERIFIED",
            "binding_terms_ready": True,
            "billing_model": policy.billing_model,
            "price_basis": {
                "amount_cents": policy.amount_cents,
                "unit": policy.unit,
                "approval_reference": (
                    "founder_approval:2026-09-23:"
                    "commercial_pricing_ladder_v1"
                ),
            },
        })
    products.append({
        "product_code": "managed_service",
        "catalog_state": "VERIFIED",
        "version_state": "VERIFIED",
        "binding_terms_ready": True,
        "billing_model": "flat_pilot",
        "price_basis": {
            "amount_cents": 150000,
            "unit": "flat",
        },
    })
    return {"products": products}


def test_live_pricing_matches_founder_policy():
    result = verify_catalog_snapshot(
        snapshot(),
        observed_at=datetime(2026, 9, 23, tzinfo=timezone.utc),
    )

    assert result["expected_product_count"] == 13
    assert result["drift_count"] == 0
    assert result["pricing_matches_approved_policy"] is True
    assert result["actual_revenue"] is False


def test_price_drift_is_detected():
    value = snapshot()
    row = next(
        item
        for item in value["products"]
        if item["product_code"] == "local_search_grid"
    )
    row["price_basis"]["amount_cents"] = 12345

    result = verify_catalog_snapshot(
        value,
        observed_at=datetime(2026, 9, 23, tzinfo=timezone.utc),
    )

    assert result["drift_count"] == 1
    assert result["pricing_matches_approved_policy"] is False
    drift = next(
        row for row in result["checks"]
        if row["product_code"] == "local_search_grid"
    )
    assert drift["state"] == "DRIFT"
