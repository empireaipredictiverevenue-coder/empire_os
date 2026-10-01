from empire_os.supply_quality_twin import (
    SupplyQualityObservation,
    build_supply_quality_twin,
)


def obs(
    key,
    supply_id,
    *,
    sources=("overpass_osm",),
    attributed=None,
    healthy=True,
    identity=True,
    delivered=True,
    buyer=True,
    revenue=10000,
    cost=4000,
):
    return SupplyQualityObservation(
        observation_key=key,
        supply_id=supply_id,
        source_keys=sources,
        attributed_source_key=attributed,
        product_key="permit_intelligence",
        market_key="roofing:austin",
        source_healthy=healthy,
        identity_accepted=identity,
        delivered=delivered,
        buyer_accepted=buyer,
        recognized_revenue_cents=revenue,
        observed_cost_cents=cost,
        evidence_refs=(f"evidence:{key}",),
    )


def build(rows):
    return build_supply_quality_twin(
        rows,
        source_key="overpass_osm",
        product_key="permit_intelligence",
        market_key="roofing:austin",
    )


def test_replay_is_idempotent_by_observation_key():
    row = obs("o1", "s1")
    twin = build([row, row])

    assert twin.unique_supply_count == 1
    assert twin.attributed_commercial_outcome_count == 1
    assert twin.attributed_recognized_revenue_cents == 10000


def test_multi_source_outcome_is_not_double_attributed_without_evidence():
    twin = build([
        obs(
            "o1",
            "s1",
            sources=("overpass_osm", "biz_search"),
            attributed=None,
        )
    ])

    assert twin.unique_supply_count == 1
    assert twin.unattributed_multi_source_count == 1
    assert twin.attributed_commercial_outcome_count == 0
    assert twin.attributed_recognized_revenue_cents == 0


def test_explicit_multi_source_attribution_is_counted_once():
    twin = build([
        obs(
            "o1",
            "s1",
            sources=("overpass_osm", "biz_search"),
            attributed="overpass_osm",
        )
    ])

    assert twin.attributed_commercial_outcome_count == 1
    assert twin.attributed_realized_gp_cents == 6000


def test_missing_cost_preserves_unknown_gross_profit():
    twin = build([obs("o1", "s1", cost=None)])

    assert twin.attributed_recognized_revenue_cents == 10000
    assert twin.attributed_observed_cost_cents is None
    assert twin.attributed_realized_gp_cents is None
    assert "observed_cost_evidence_incomplete" in twin.blockers


def test_healthy_source_does_not_establish_commercial_quality():
    twin = build([
        obs(
            "o1",
            "s1",
            healthy=True,
            identity=True,
            delivered=None,
            buyer=None,
            revenue=None,
            cost=None,
        )
    ])

    assert twin.source_healthy_count == 1
    assert twin.commercial_quality_inferred is False
    assert twin.buyer_acceptance_probability_inferred is False
    assert "buyer_outcomes_unobserved" in twin.blockers


def test_identity_acceptance_does_not_imply_buyer_acceptance():
    twin = build([
        obs(
            "o1",
            "s1",
            identity=True,
            delivered=True,
            buyer=False,
            revenue=None,
            cost=None,
        )
    ])

    assert twin.identity_accepted_count == 1
    assert twin.buyer_outcome_observed_count == 1
    assert twin.buyer_accepted_count == 0


def test_twin_never_grants_operational_authority():
    twin = build([obs("o1", "s1")])

    assert twin.source_policy_mutation is False
    assert twin.canonical_writes is False
    assert twin.allocation_execution is False
    assert twin.revenue_recognition is False
    assert twin.execution_authority == "none"
