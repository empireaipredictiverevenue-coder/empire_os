import pytest

from empire_os.market_domination import (
    analyse_market_capture,
    compare_adjacent_corridors,
    rank_market_portfolio,
)


def snapshot(corridor="roofing:manchester", attraction=.8):
    return {
        "market_key": "uk-home-services",
        "territory_key": "manchester",
        "corridor_key": corridor,
        "product_key": "territory-seat",
        "demand_strength": attraction,
        "buyer_capacity_strength": .8,
        "competition_inverse": .6,
        "product_fit": .9,
        "data_advantage": .9,
        "search_authority": .7,
        "ai_visibility": .6,
        "partner_density": .7,
        "margin_potential": .85,
        "retention_expansion": .8,
        "confidence": .8,
        "verified_buyer_count": 3,
        "verified_capacity_units": 25,
        "verified_outcome_count": 8,
        "repeat_outcome_count": 3,
        "expected_gross_profit_cents": 500000,
        "realized_gross_profit_cents": 350000,
        "time_to_revenue_days": 21,
        "downside_cents": 75000,
        "evidence_refs": ["market:1", "buyer:1", "outcome:1"],
    }


def test_market_capture_separates_prediction_from_realized_truth():
    result = analyse_market_capture(snapshot())
    assert result["expected_economics"]["prediction_only"] is True
    assert result["expected_economics"]["actual_revenue"] is False
    assert result["realized_economics"]["realized_gross_profit_cents"] == 350000
    assert result["market_entry_execution"] is False
    assert result["execution_authority"] == "none"


def test_stage_can_reach_expand_without_claiming_market_control():
    result = analyse_market_capture(snapshot())
    assert result["capture_stage"]["stage"] == "EXPAND"
    assert result["capture_stage"]["observed_market_control"] is False
    assert result["market_control_claimed"] is False
    assert result["market_control_claim_available"] is False
    assert result["next_strategic_objective"]["objective"] == "review_adjacent_corridor_expansion"
    assert result["moat_gaps"]
    assert all("dimension" in row for row in result["moat_gaps"])


def test_market_share_must_be_explicit_observation():
    row = snapshot()
    row["observed_market_share"] = .18
    result = analyse_market_capture(row)
    assert result["observed_market_share"] == .18
    assert result["market_control_claim_available"] is True
    assert result["market_control_claimed"] is False


def test_no_real_outcomes_stays_establish_not_expand():
    row = snapshot()
    row["verified_outcome_count"] = 0
    row["repeat_outcome_count"] = 0
    row["realized_gross_profit_cents"] = None
    result = analyse_market_capture(row)
    assert result["capture_stage"]["stage"] == "ESTABLISH"
    assert result["expansion_review_ready"] is False
    assert "capture_stage_not_expand" in result["expansion_blockers"]


def test_negative_realized_gp_is_preserved_and_blocks_expansion():
    row = snapshot()
    row["realized_gross_profit_cents"] = -25000
    result = analyse_market_capture(row)
    assert result["realized_economics"]["realized_gross_profit_cents"] == -25000
    assert result["capture_stage"]["stage"] == "PROVE"
    assert result["expansion_review_ready"] is False
    assert "positive_realized_gross_profit_required" in result["expansion_blockers"]


def test_missing_market_dimensions_remain_unknown():
    row = snapshot()
    row["search_authority"] = None
    result = analyse_market_capture(row)
    assert result["market_attractiveness"]["available"] is False
    assert "search_authority" in result["market_attractiveness"]["missing"]
    assert result["defensibility"]["available"] is False
    gap = next(x for x in result["moat_gaps"] if x["dimension"] == "search_authority")
    assert gap["status"] == "unknown"
    assert gap["observed_value"] is None


def test_portfolio_ranking_prefers_stronger_observed_market():
    a = snapshot("roofing:manchester", .9)
    b = snapshot("roofing:liverpool", .55)
    b["territory_key"] = "liverpool"
    result = rank_market_portfolio([b, a])
    assert result["markets"][0]["identity"]["corridor_key"] == "roofing:manchester"
    assert result["markets"][0]["portfolio_rank"] == 1
    assert result["allocation_execution"] is False


def test_duplicate_market_snapshot_rejected():
    row = snapshot()
    with pytest.raises(ValueError, match="duplicate"):
        rank_market_portfolio([row, row])


def test_adjacency_requires_mature_current_corridor():
    current = snapshot()
    candidate = snapshot("roofing:liverpool", .75)
    candidate["territory_key"] = "liverpool"
    result = compare_adjacent_corridors(current=current, candidates=[candidate])
    assert result["candidates"][0]["adjacency_review_ready"] is True
    assert result["expansion_execution"] is False

    immature = snapshot()
    immature["verified_outcome_count"] = 0
    immature["repeat_outcome_count"] = 0
    immature["realized_gross_profit_cents"] = None
    blocked = compare_adjacent_corridors(current=immature, candidates=[candidate])
    assert blocked["candidates"][0]["adjacency_review_ready"] is False
    assert "current_corridor_not_mature_enough_for_adjacency_review" in blocked["candidates"][0]["blockers"]
