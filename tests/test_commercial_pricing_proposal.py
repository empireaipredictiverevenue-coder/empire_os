from empire_os.commercial_pricing_policy import LAUNCH_PRICING
from scripts.propose_commercial_pricing_ladder import build_rpc_payload


def test_pricing_rpc_payload_requires_founder_approved_basis():
    policy = LAUNCH_PRICING[0]
    payload = build_rpc_payload(
        policy,
        "founder_approval:pricing_ladder:2026-09-23",
    )

    assert payload["p_product_code"] == policy.product_code
    assert payload["p_price_basis"]["state"] == "VERIFIED"
    assert payload["p_price_basis"]["source_type"] == "founder_approved"
    assert payload["p_acquisition_cost_basis"]["state"] == "VERIFIED"
    assert payload["p_fulfilment_cost_basis"]["state"] == "VERIFIED"
    assert payload["p_margin_policy"]["state"] == "VERIFIED"
    assert payload["p_provenance"]["actual_revenue"] is False
    assert payload["p_provenance"]["costs_are_policy_ceilings"] is True


def test_pricing_rpc_payload_preserves_serp_usage_allowance():
    policy = next(
        row for row in LAUNCH_PRICING
        if row.product_code == "serp_intelligence_api"
    )
    payload = build_rpc_payload(
        policy,
        "founder_approval:pricing_ladder:2026-09-23",
    )

    assert payload["p_price_basis"]["included_units"] == 10000
    assert payload["p_price_basis"]["overage_amount_cents"] == 1
