from empire_os.commercial_pricing_policy import (
    LAUNCH_PRICING,
    build_launch_pricing_proposal,
)


EXPECTED_CODES = {
    "authority_intelligence",
    "competitor_search_gap",
    "content_protection",
    "geo_ai_visibility",
    "local_search_grid",
    "permit_intelligence",
    "private_capital_rollup",
    "property_intelligence",
    "search_growth_command",
    "search_opportunity_map",
    "serp_intelligence_api",
    "technical_search_audit",
}


def test_pricing_covers_all_current_unpriced_products():
    assert {row.product_code for row in LAUNCH_PRICING} == EXPECTED_CODES


def test_pricing_meets_its_own_margin_policy():
    for row in LAUNCH_PRICING:
        assert row.amount_cents > 0
        assert row.acquisition_cost_ceiling_cents >= 0
        assert row.fulfilment_cost_ceiling_cents >= 0
        assert row.policy_margin_bps >= row.minimum_margin_bps


def test_pricing_is_non_binding_until_exact_founder_approval():
    result = build_launch_pricing_proposal()

    assert result["binding"] is False
    assert result["founder_approval_required"] is True
    assert result["database_mutation_authorized"] is False
    assert result["actual_revenue"] is False
    assert result["execution_authority"] == "none"


def test_managed_service_verified_price_is_not_repriced():
    result = build_launch_pricing_proposal()
    existing = result["existing_verified_product_unchanged"]

    assert existing["product_code"] == "managed_service"
    assert existing["amount_cents"] == 150000
    assert existing["billing_model"] == "flat_pilot"


def test_serp_api_has_bounded_launch_usage_policy():
    row = next(
        policy
        for policy in LAUNCH_PRICING
        if policy.product_code == "serp_intelligence_api"
    )

    assert row.amount_cents == 9900
    assert row.included_units == 10000
    assert row.overage_amount_cents == 1
