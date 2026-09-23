import empire_os.solar_economics_policy as policy


def test_policy_proposal_covers_all_localized_markets():
    result = policy.build_market_economics_proposal()

    assert result["market_count"] == 13
    assert result["policy_state"] == "PROPOSED"
    assert result["acquisition_ceiling_bps"] == 2000
    assert result["fulfilment_ceiling_bps"] == 2000
    assert result["minimum_margin_bps"] == 5500
    assert result["ceiling_case_margin_bps"] == 6000
    assert result["policy_buffer_bps"] == 500
    assert result["founder_approval_required"] is True
    assert result["catalog_mutation_authorized"] is False
    assert result["binding_terms_ready"] is False
    assert result["actual_revenue"] is False


def test_gb_policy_proposal_uses_local_currency_and_policy_ceilings():
    result = policy.build_market_economics_proposal()
    gb = next(
        row for row in result["markets"]
        if row["country_code"] == "GB"
    )

    assert gb["product_code"] == "solar_opportunity_map_gb"
    assert gb["currency"] == "GBP"
    assert gb["price_minor"] == 24900
    assert gb["acquisition_cost_ceiling"]["amount_minor"] == 4980
    assert gb["fulfilment_cost_ceiling"]["amount_minor"] == 4980
    assert gb["ceiling_case"]["contribution_minor"] == 14940
    assert gb["ceiling_case"]["realized_margin_bps"] == 6000
    assert gb["ceiling_case"]["margin_buffer_bps"] == 500
    assert gb["founder_approved"] is False
    assert gb["binding_terms_ready"] is False


def test_policy_proposal_never_claims_observed_costs():
    result = policy.build_market_economics_proposal()

    assert result["proposal_is_observed_cost"] is False
    assert result["resource_observations_used_as_cash_cost"] is False
    for row in result["markets"]:
        assert row["acquisition_cost_ceiling"]["observed_cost_claim"] is False
        assert row["fulfilment_cost_ceiling"]["observed_cost_claim"] is False
        assert row["margin_policy"]["state"] == "PROPOSED"
