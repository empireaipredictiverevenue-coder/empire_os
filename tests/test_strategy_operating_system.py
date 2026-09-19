import pytest

from empire_os.strategy_operating_system import (
    rank_keyword_portfolio,
    review_ai_capability,
    review_market_thesis,
    review_strategic_bet,
)


def full_market():
    return {
        "market_key": "roofing:manchester",
        "customer_problem": .9,
        "willingness_to_pay": .8,
        "demand_supply_imbalance": .8,
        "buyer_capacity": .75,
        "competition_inverse": .6,
        "data_advantage": .9,
        "product_fit": .9,
        "gtm_accessibility": .8,
        "margin_potential": .85,
        "retention_expansion": .75,
        "moat_potential": .9,
        "confidence": .8,
        "evidence_refs": ["market:1"],
    }


def test_market_thesis_is_recommendation_only():
    result = review_market_thesis(full_market())
    assert result["available"] is True
    assert result["recommendation"] in {"ENTER", "TEST", "WATCH", "AVOID"}
    assert result["market_entry_execution"] is False
    assert result["execution_authority"] == "none"


def test_market_thesis_missing_input_stays_unknown():
    row = full_market()
    row["buyer_capacity"] = None
    result = review_market_thesis(row)
    assert result["available"] is False
    assert result["recommendation"] is None
    assert "buyer_capacity" in result["missing"]


def test_strategic_bet_requires_kill_and_learning_criteria():
    result = review_strategic_bet({
        "bet_id": "bet-1",
        "bet_type": "new_market",
        "thesis": "This corridor may support profitable seats.",
        "evidence_refs": ["e:1"],
        "owner": "strategy",
    })
    assert result["review_ready"] is False
    assert "kill_criteria_required" in result["blockers"]
    assert "learning_objective_required" in result["blockers"]
    assert result["capital_commitment"] is False


def keyword(name, score=.8):
    return {
        "keyword": name,
        "observed_demand": score,
        "commercial_intent": score,
        "product_fit": score,
        "buyer_fit": score,
        "coverage_gap": score,
        "competitor_gap": score,
        "ai_citation_gap": score,
        "conversion_evidence": score,
        "strategic_category_value": score,
        "confidence": score,
        "evidence_refs": [f"kw:{name}"],
    }


def test_keyword_portfolio_ranks_observed_evidence_only():
    result = rank_keyword_portfolio([
        keyword("predictive revenue", .9),
        keyword("generic ai tool", .4),
    ])
    assert result["ranked"][0]["keyword"] == "predictive revenue"
    assert result["publishing_enabled"] is False
    assert result["indexation_enabled"] is False


def test_keyword_missing_metrics_not_invented():
    row = keyword("permit intelligence")
    row["observed_demand"] = None
    result = rank_keyword_portfolio([row])
    assert result["ranked"] == []
    assert result["unscored"][0]["available"] is False


def test_ai_strategy_recommends_mode_without_activation():
    result = review_ai_capability({
        "capability_key": "market-entity-resolution",
        "problem": "Resolve company identity across fragmented sources.",
        "strategic_advantage": "Proprietary graph improves downstream prediction.",
        "evidence_refs": ["e:entity:1"],
        "strategic_value": .9,
        "proprietary_data_advantage": .95,
        "expected_quality_gain": .8,
        "privacy_importance": .8,
        "cost_sensitivity": .7,
        "switching_flexibility": .2,
        "confidence": .8,
    })
    assert result["review_ready"] is True
    assert result["recommended_mode"] in {"BUILD", "BUY", "HYBRID", "WATCH"}
    assert result["provider_activation"] is False
    assert result["model_promotion"] is False


def test_duplicate_keyword_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        rank_keyword_portfolio([keyword("x"), keyword("x")])
