from empire_os.commercial_terms_readiness import (
    CommercialTermsReadinessEvidence,
    review_commercial_terms_readiness,
)


def evidence(**overrides):
    data = {
        "closer_case_id": "case-1",
        "fulfilment_order_id": "order-1",
        "buyer_id": "buyer-1",
        "prospect_id": "prospect-1",
        "order_state": "qualified",
        "buyer_conversation_observed": True,
        "capacity_intake_state": "complete",
        "capacity_evidence_ref": "capacity:1",
        "territory": "Austin",
        "daily_cap": 10,
        "delivery_route": "webhook",
        "proposed_price_cents": 12000,
        "verified_price_evidence_ref": "price:verified:1",
        "acquisition_cost_cents": 2500,
        "acquisition_cost_evidence_ref": "cost:acq:1",
        "fulfilment_cost_cents": 1500,
        "fulfilment_cost_evidence_ref": "cost:fulfil:1",
    }
    data.update(overrides)
    return CommercialTermsReadinessEvidence(**data)


def test_ready_packet_preserves_canonical_settlement_and_margin():
    review = review_commercial_terms_readiness(evidence())
    assert review.ready_for_terms_proposal is True
    assert review.blockers == ()
    assert review.expected_margin_cents == 8000
    assert review.terms_packet["currency"] == "USD"
    assert review.terms_packet["settlement_asset"] == "USDT"
    assert review.terms_packet["settlement_chain"] == "BSC"
    assert review.terms_packet["binding"] is False
    assert review.pricing_authority == "none"
    assert review.acceptance_authority == "none"
    assert review.actual_revenue is False


def test_model_price_without_verified_reference_is_not_offer_ready():
    review = review_commercial_terms_readiness(
        evidence(verified_price_evidence_ref=None)
    )
    assert review.ready_for_terms_proposal is False
    assert "verified_price_evidence_missing" in review.blockers
    assert review.terms_packet is None


def test_missing_observed_costs_blocks_terms():
    review = review_commercial_terms_readiness(
        evidence(
            acquisition_cost_cents=None,
            acquisition_cost_evidence_ref=None,
            fulfilment_cost_cents=None,
            fulfilment_cost_evidence_ref=None,
        )
    )
    assert review.ready_for_terms_proposal is False
    assert "acquisition_cost_missing" in review.blockers
    assert "fulfilment_cost_missing" in review.blockers


def test_nonpositive_margin_is_blocked():
    review = review_commercial_terms_readiness(
        evidence(
            proposed_price_cents=3000,
            acquisition_cost_cents=2000,
            fulfilment_cost_cents=1500,
        )
    )
    assert review.ready_for_terms_proposal is False
    assert "positive_expected_margin_required" in review.blockers
    assert review.expected_margin_cents == -500


def test_incomplete_capacity_never_promotes_to_terms():
    review = review_commercial_terms_readiness(
        evidence(
            capacity_intake_state="partial",
            capacity_evidence_ref=None,
            territory=None,
            daily_cap=None,
            delivery_route=None,
        )
    )
    assert review.ready_for_terms_proposal is False
    assert "complete_buyer_capacity_evidence_missing" in review.blockers
    assert "buyer_territory_missing" in review.blockers
    assert "buyer_daily_capacity_missing" in review.blockers
    assert "buyer_delivery_route_missing" in review.blockers
