from empire_os.opportunity_evidence_normalizer import (
    build_normalized_signal_batch,
    normalize_candidate,
)


def market_candidate():
    return {
        "opportunity_key": "market:roofing:denver",
        "opportunity_class": "market_research",
        "niche": "roofing",
        "metro": "denver",
        "offer_key": "managed_service",
    }


def predictive_intelligence():
    return {
        "product_estimates": {
            "managed_service": {
                "product_code": "managed_service",
                "terminal_outcome_count": 25,
                "success_count": 15,
                "failure_count": 10,
                "probability_available": True,
                "probability_success": 0.592593,
                "uncertainty": 0.181,
                "confidence": 0.638,
                "uncertainty_semantics": (
                    "half_width_of_95pct_wilson_interval"
                ),
                "confidence_semantics": (
                    "precision_proxy_one_minus_95pct_wilson_interval_width"
                ),
                "time_to_revenue_available": True,
                "time_to_revenue_days": 12.5,
                "candidate_probability_is_product_cohort_baseline": True,
                "candidate_specific_causal_probability_claimed": False,
                "evidence_refs": [
                    "canonical:commercial_outcomes",
                ],
            }
        }
    }


def market_gps():
    return {
        "markets": [{
            "niche": "roofing",
            "metro": "denver",
            "commercial_reply_count": 2,
            "commercial_terms_count": 1,
            "verified_payment_count": 0,
            "approved_buyer_count": 3,
            "product_candidate": "managed_service",
            "economics_scenario": {
                "available": True,
                "pilot_price_cents": 150000,
                "acquisition_cost_ceiling_cents": 30000,
                "fulfilment_cost_ceiling_cents": 30000,
                "policy_cost_ceiling_cents": 60000,
                "product_code": "managed_service",
            },
        }]
    }


def test_market_normalization_uses_observed_commercial_stages():
    row = normalize_candidate(
        market_candidate(),
        market_gps=market_gps(),
    )
    signals = row["normalized_signals"]
    assert signals["buyer_intent"] == 0.9
    assert signals["demand"] == 0.9
    assert signals["margin_potential"] == 0.6
    assert signals["distribution_strength"] == 0.8
    assert signals["build_complexity"] == 0.2
    assert signals["distribution_path"] == "approved_buyer_network"
    assert row["score_evidence"]["buyer_intent"][
        "observed_truth"
    ] is True
    assert row["score_evidence"]["margin_potential"][
        "semantic_class"
    ] == "policy_scenario"
    assert row["search_result_counts_used_as_scores"] is False


def test_public_pain_does_not_become_buyer_intent():
    row = normalize_candidate({
        "opportunity_key": "community_pain:search_visibility",
        "opportunity_class": "community_pain",
        "average_intent_score": 80,
        "high_intent_mentions": 5,
        "offer_key": "search_growth_command",
    })
    assert row["normalized_signals"]["buyer_intent"] is None
    assert row["normalized_signals"]["demand"] is None
    assert row["buyer_intent_inferred_from_public_pain"] is False


def test_competitor_gap_does_not_become_demand():
    row = normalize_candidate({
        "opportunity_key": "competitor_coverage:roofing:denver",
        "opportunity_class": "competitive_research_gap",
        "research_gap_company_count": 20,
    })
    assert row["normalized_signals"]["demand"] is None
    assert row["competitor_gaps_used_as_demand"] is False


def test_batch_reports_partial_normalization_without_claiming_revenue():
    payload = build_normalized_signal_batch(
        {"candidates": [market_candidate()]},
        market_gps=market_gps(),
    )
    assert payload["candidate_count"] == 1
    assert payload["candidates_with_any_normalized_score"] == 1
    assert payload["total_normalized_scores"] == 5
    assert payload["market_share_inferred"] is False
    assert payload["revenue_inferred"] is False
    assert payload["execution_authority"] == "none"


def test_verified_predictive_cohort_populates_quant_inputs():
    row = normalize_candidate(
        market_candidate(),
        market_gps=market_gps(),
        predictive_intelligence=predictive_intelligence(),
    )
    quant = row["quant_inputs"]
    assert quant["conditional_revenue_cents"] == 150000.0
    assert quant["fixed_cost_cents"] == 30000.0
    assert quant["success_cost_cents"] == 30000.0
    assert quant["probability_success"] == 0.592593
    assert quant["uncertainty"] == 0.181
    assert quant["confidence"] == 0.638
    assert quant["time_to_revenue_days"] == 12.5
    assert row["probability_modeled_from_verified_outcomes"] is True
    assert row["quant_probability_inferred"] is False
    evidence = row["quant_input_evidence"]["predictive_intelligence"]
    assert evidence[
        "candidate_probability_is_product_cohort_baseline"
    ] is True
    assert evidence[
        "candidate_specific_causal_probability_claimed"
    ] is False


def test_unavailable_predictive_cohort_does_not_fill_probability():
    unavailable = predictive_intelligence()
    unavailable["product_estimates"]["managed_service"].update({
        "probability_available": False,
        "probability_success": None,
        "uncertainty": None,
        "confidence": None,
        "time_to_revenue_available": False,
        "time_to_revenue_days": None,
    })
    row = normalize_candidate(
        market_candidate(),
        market_gps=market_gps(),
        predictive_intelligence=unavailable,
    )
    assert row["quant_inputs"]["probability_success"] is None
    assert row["probability_modeled_from_verified_outcomes"] is False
