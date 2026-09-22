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
                "policy_cost_ceiling_cents": 60000,
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
