from empire_os.predictive_revenue_private_deployment import (
    PRIVATE_DEPLOYMENT_SCOPE,
    private_deployment_economics,
)


def test_private_deployment_250k_scope_economics():
    result = private_deployment_economics()

    assert result["price_cents"] == 25_000_000
    assert result["direct_fulfilment_cost_ceiling_cents"] == 7_500_000
    assert result["acquisition_cost_ceiling_cents"] == 2_500_000
    assert result["gross_margin_bps_at_ceiling"] == 7000
    assert result["contribution_margin_bps_at_ceiling"] == 6000
    assert result["observed_cost_claim"] is False
    assert result["actual_revenue"] is False
    assert len(PRIVATE_DEPLOYMENT_SCOPE) == 8
