from empire_os.opportunity_factory import OpportunityCandidate, assess_opportunity


def candidate(**overrides):
    values = dict(
        opportunity_key="storm-dfw-roofing",
        niche="roofing",
        trigger="hail",
        offer_key="storm-revenue-strike",
        distribution_path="governed_outbound",
        evidence_refs=("weather:1", "search:1", "business:1"),
        buyer_intent=.9,
        demand=.8,
        urgency=.9,
        margin_potential=.7,
        distribution_strength=.8,
        data_advantage=.9,
        fulfilment_readiness=.8,
        build_complexity=.3,
    )
    values.update(overrides)
    return OpportunityCandidate(**values)


def test_strong_evidenced_opportunity_requests_small_mvp():
    result = assess_opportunity(candidate())
    assert result.score >= 65
    assert result.decision == "build_smallest_useful_mvp"
    assert result.next_event == "mvp_build_requested"
    assert result.revenue_verified is False


def test_offer_and_distribution_must_exist_before_build():
    result = assess_opportunity(candidate(offer_key="", distribution_path=""))
    assert result.decision == "research"
    assert "offer_not_attached" in result.reasons
    assert "distribution_not_attached" in result.reasons


def test_weak_buyer_intent_is_parked_not_faked_into_revenue():
    result = assess_opportunity(candidate(
        buyer_intent=.1, demand=.2, urgency=.1,
        margin_potential=.2, distribution_strength=.1,
        data_advantage=.1, fulfilment_readiness=.2,
        build_complexity=.8,
    ))
    assert result.decision == "park"
    assert result.revenue_verified is False
