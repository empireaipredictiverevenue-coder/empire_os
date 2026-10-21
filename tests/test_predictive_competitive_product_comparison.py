"""Competitive product comparisons must not masquerade as approved price ROI."""
from __future__ import annotations

from decimal import Decimal
import json
import pytest

from empire_os.predictive_revenue_products import PREDICTIVE_REVENUE_PRODUCTS
from empire_os.predictive_competitive_product_comparison import (
    BENCHMARKS, REQUIRED_JUSTIFICATION, PRODUCT_OVERLAP,
    compare_predictive_enterprise_products,
)


def test_every_original_founder_product_keeps_exact_price_and_includes_competitors():
    r = compare_predictive_enterprise_products()
    assert r["product_count"] == len(PREDICTIVE_REVENUE_PRODUCTS) == 5
    assert r["comparator_count"] == 6
    assert r["astra_gpt6_independent_review"] == "NOT_EXECUTED"
    assert r["seats_and_bespoke_projects_not_normalized_to_one_price"] is True
    assert r["customer_price_approval_or_sales_execution"] is False
    assert r["original_database_or_runtime_queried"] is False
    assert r["execution_authority"] == "none"
    by_code = {p["product_code"]: p for p in r["products"]}
    for original in PREDICTIVE_REVENUE_PRODUCTS:
        p = by_code[original.product_code]
        assert p["price_usd_cents"] == original.deployment_price_cents
        assert p["approved_price_type"] == original.price_type
        assert p["founder_price_state_preserved"] == "FOUNDER_APPROVED"
        assert len(p["competitors"]) == 6
        assert len(p["justification_requirements"]) == len(REQUIRED_JUSTIFICATION)
        assert set(p["proposed_scope_categories"]) == set(PRODUCT_OVERLAP[original.product_code])
        assert p["price_justification_status"] == "UNVERIFIED_PENDING_SCOPE_COST_AND_CUSTOMER_VALUE"
        for value in (
            "verified_cost_of_delivery_usd_cents",
            "verified_customer_value_usd_cents",
            "verified_gross_margin_percent",
        ):
            assert p[value] is None
        for value in (
            "empirical_value_or_roi_proven", "real_customer_acceptance_test_passed",
            "scoped_binding_terms_verified", "competitive_price_ordering_is_valid",
            "automatic_price_change_authorized",
            "customer_claim_or_public_announcement_authorized",
        ):
            assert p[value] is False


def test_vendor_public_prices_keep_units_and_quote_unknown():
    report=compare_predictive_enterprise_products()
    by_vendor={row["vendor"]: row for row in report["comparators"]}
    assert by_vendor["HubSpot"]["public_unit_price_usd"] == 150
    assert by_vendor["Microsoft"]["public_unit_price_usd"] == 105
    assert by_vendor["Zoho"]["public_unit_price_usd"] == 40
    assert by_vendor["Databox"]["public_unit_price_usd"] == 249
    assert by_vendor["Clari"]["public_unit_price_usd"] is None
    assert by_vendor["Gong"]["public_unit_price_usd"] is None
    assert by_vendor["HubSpot"]["billing"] == "USD_PER_USER_MONTH_ANNUAL"
    assert by_vendor["Databox"]["billing"] == "USD_PER_MONTH_PLATFORM"
    for item in report["comparators"]:
        assert item["source_url"].startswith("https://")
        assert item["observed_as_of"] == "2026-10-21"
        assert item["contract_equivalence_verified"] is False
        assert item["independent_feature_parity_verified"] is False


def test_comparison_is_deterministic_and_does_not_mint_claims():
    a = compare_predictive_enterprise_products()
    b = compare_predictive_enterprise_products()
    assert a == b
    assert json.dumps(a, sort_keys=True, allow_nan=False) == json.dumps(b, sort_keys=True, allow_nan=False)
    assert all(
        not row["actual_feature_parity_verified"]
        and not row["comparable_total_contract_cost_verified"]
        for product in a["products"] for row in product["competitors"]
    )


def test_catalogue_drift_refused_not_silently_omitted(monkeypatch):
    from empire_os import predictive_competitive_product_comparison as mod
    monkeypatch.setattr(mod, "PRODUCT_OVERLAP", {"fake": ("crm",)})
    with pytest.raises(ValueError, match="ladder"):
        mod.compare_predictive_enterprise_products()
