import empire_os.solar_economics_policy as policy


def test_policy_proposal_covers_all_localized_markets():
    result = policy.build_market_economics_proposal()

    assert result["market_count"] == 13
    assert result["policy_state"] == "FOUNDER_APPROVED"
    assert result["acquisition_ceiling_bps"] == 2000
    assert result["fulfilment_ceiling_bps"] == 2000
    assert result["minimum_margin_bps"] == 5500
    assert result["ceiling_case_margin_bps"] == 6000
    assert result["policy_buffer_bps"] == 500
    assert result["founder_approval_required"] is False
    assert result["founder_approval_date"] == "2026-09-23"
    assert result["catalog_mutation_authorized"] is True
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
    assert gb["founder_approved"] is True
    assert gb["binding_terms_ready"] is False


def test_policy_proposal_never_claims_observed_costs():
    result = policy.build_market_economics_proposal()

    assert result["proposal_is_observed_cost"] is False
    assert result["resource_observations_used_as_cash_cost"] is False
    for row in result["markets"]:
        assert row["acquisition_cost_ceiling"]["observed_cost_claim"] is False
        assert row["fulfilment_cost_ceiling"]["observed_cost_claim"] is False
        assert row["margin_policy"]["state"] == "FOUNDER_APPROVED"


def test_catalog_basis_preserves_policy_ceiling_semantics():
    basis = policy.catalog_economics_basis("GB")

    assert basis["product_code"] == "solar_opportunity_map_gb"
    assert basis["price_basis"]["state"] == "VERIFIED"
    assert basis["acquisition_cost_basis"]["state"] == "VERIFIED"
    assert basis["acquisition_cost_basis"]["basis_type"] == "policy_ceiling"
    assert basis["acquisition_cost_basis"]["observed_cost_claim"] is False
    assert basis["fulfilment_cost_basis"]["basis_type"] == "policy_ceiling"
    assert basis["fulfilment_cost_basis"]["observed_cost_claim"] is False
    assert basis["margin_policy"]["state"] == "VERIFIED"
    assert basis["margin_policy"]["basis_type"] == "founder_policy"
    assert basis["margin_policy"]["minimum_margin_bps"] == 5500
