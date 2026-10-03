import pytest

from empire_os.digital_avatar_pricing_economics_proposal import (
    DIGITAL_AVATAR_PRICING_PROPOSALS,
    MINIMUM_MARGIN_BPS,
    POLICY_REFERENCE,
    TARGET_POLICY_MARGIN_BPS,
    AvatarPricingPolicyProposal,
    build_digital_avatar_pricing_proposal,
)


def by_key(key):
    return next(
        value
        for value in DIGITAL_AVATAR_PRICING_PROPOSALS
        if value.package_key == key
    )


def test_exact_founder_pricing_proposal_ladder():
    copilot = by_key("copilot")
    workforce = by_key("workforce")
    white_label = by_key("white_label_workforce")

    assert copilot.monthly_price_cents == 150_000
    assert copilot.implementation_fee_cents == 150_000
    assert copilot.included_active_avatars == 1
    assert copilot.included_verified_meetings_per_month == 40
    assert copilot.proposed_concurrency_entitlement == 1
    assert copilot.overage_per_verified_meeting_cents == 3_500

    assert workforce.monthly_price_cents == 500_000
    assert workforce.implementation_fee_cents == 500_000
    assert workforce.included_active_avatars == 5
    assert workforce.included_verified_meetings_per_month == 150
    assert workforce.proposed_concurrency_entitlement == 3
    assert workforce.overage_per_verified_meeting_cents == 3_000

    assert white_label.monthly_price_cents == 1_250_000
    assert white_label.implementation_fee_cents == 1_500_000
    assert white_label.included_active_avatars == 15
    assert white_label.included_verified_meetings_per_month == 400
    assert white_label.proposed_concurrency_entitlement == 10
    assert white_label.overage_per_verified_meeting_cents == 2_500


def test_all_proposals_meet_target_and_minimum_policy_margin():
    assert TARGET_POLICY_MARGIN_BPS == 7500
    assert MINIMUM_MARGIN_BPS == 7000
    for proposal in DIGITAL_AVATAR_PRICING_PROPOSALS:
        proposal.validate()
        assert proposal.policy_margin_bps == 7500
        assert proposal.policy_margin_bps >= proposal.minimum_margin_bps
        assert proposal.policy_contribution_cents > 0


def test_policy_cost_ceilings_are_not_claimed_as_observed_actual_costs():
    for proposal in DIGITAL_AVATAR_PRICING_PROPOSALS:
        payload = proposal.as_proposal_dict()
        assert payload["price_basis"]["state"] == "PROPOSED"
        assert payload["price_basis"]["observed_historical_transaction_price"] is False
        assert payload["acquisition_cost_basis"]["state"] == "PROPOSED"
        assert payload["acquisition_cost_basis"]["observed_actual"] is False
        assert payload["fulfilment_cost_basis"]["state"] == "PROPOSED"
        assert payload["fulfilment_cost_basis"]["observed_actual"] is False
        assert payload["margin_policy"]["state"] == "PROPOSED"
        assert payload["binding"] is False


def test_proposal_has_no_database_checkout_payment_or_revenue_authority():
    payload = build_digital_avatar_pricing_proposal()
    assert payload["policy_reference"] == POLICY_REFERENCE
    assert payload["custom_enterprise_recurring_floor_cents"] == 1_500_000
    assert payload["custom_enterprise_floor_state"] == "PROPOSED"
    assert payload["observed_costs_verified"] is False
    assert payload["duration_cost_benchmark_required"] is True
    assert payload["capacity_benchmark_required"] is True
    assert payload["founder_approval_required"] is True
    assert payload["database_mutation_authorized"] is False
    assert payload["binding_terms_ready"] is False
    assert payload["checkout_authorized"] is False
    assert payload["payment_authority"] == "none"
    assert payload["actual_revenue"] is False
    assert payload["execution_authority"] == "none"


def test_founder_price_approval_verifies_price_only_not_cost_margin_or_binding():
    candidate = by_key("workforce").as_founder_approved_price_candidate(
        "founder_approval:2026-10-02:digital_avatar_pricing_v1"
    )
    assert candidate["price_basis"]["state"] == "VERIFIED"
    assert candidate["price_basis"]["source_type"] == "founder_approved"
    assert candidate["price_basis"]["approval_reference"] == (
        "founder_approval:2026-10-02:digital_avatar_pricing_v1"
    )
    assert "proposal_reference" not in candidate["price_basis"]

    assert candidate["acquisition_cost_basis"]["state"] == "PROPOSED"
    assert candidate["fulfilment_cost_basis"]["state"] == "PROPOSED"
    assert candidate["margin_policy"]["state"] == "PROPOSED"
    assert candidate["binding"] is False
    assert candidate["catalog_mutation_authorized"] is False
    assert candidate["checkout_authorized"] is False
    assert candidate["payment_authority"] == "none"
    assert candidate["actual_revenue"] is False
    assert candidate["execution_authority"] == "none"


def test_founder_price_candidate_requires_explicit_approval_reference():
    with pytest.raises(
        ValueError,
        match="explicit founder pricing approval reference required",
    ):
        by_key("copilot").as_founder_approved_price_candidate("")


def test_policy_margin_below_floor_fails_closed():
    bad = AvatarPricingPolicyProposal(
        package_key="copilot",
        product_code="digital_avatar_copilot",
        monthly_price_cents=100_000,
        implementation_fee_cents=100_000,
        included_active_avatars=1,
        included_verified_meetings_per_month=10,
        proposed_concurrency_entitlement=1,
        overage_per_verified_meeting_cents=2_000,
        acquisition_cost_ceiling_cents=20_000,
        fulfilment_cost_ceiling_cents=20_000,
        minimum_margin_bps=7000,
    )
    with pytest.raises(ValueError, match="minimum policy margin"):
        bad.validate()


def test_package_product_identity_is_reconciled_against_approved_package_registry():
    bad = AvatarPricingPolicyProposal(
        package_key="workforce",
        product_code="digital_avatar_copilot",
        monthly_price_cents=500_000,
        implementation_fee_cents=500_000,
        included_active_avatars=5,
        included_verified_meetings_per_month=150,
        proposed_concurrency_entitlement=3,
        overage_per_verified_meeting_cents=3_000,
        acquisition_cost_ceiling_cents=50_000,
        fulfilment_cost_ceiling_cents=75_000,
    )
    with pytest.raises(ValueError, match="package/product mismatch"):
        bad.validate()
