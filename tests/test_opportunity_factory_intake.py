from empire_os.opportunity_factory_intake import (
    build_factory_intake,
    build_factory_intake_batch,
)


def candidate():
    return {
        "opportunity_key": "storm-dfw-roofing",
        "opportunity_class": "event_market",
        "niche": "roofing",
        "trigger": "hail",
        "offer_key": "storm-revenue-strike",
        "evidence_refs": ["weather:1"],
    }


def research():
    return {
        "opportunity_key": "storm-dfw-roofing",
        "observation_count": 2,
        "evidence_urls": [
            "https://example.com/market",
            "https://example.com/competitor",
        ],
    }


def normalized():
    return {
        "distribution_path": "governed_outbound",
        "buyer_intent": 0.9,
        "demand": 0.8,
        "urgency": 0.9,
        "margin_potential": 0.7,
        "distribution_strength": 0.8,
        "data_advantage": 0.9,
        "fulfilment_readiness": 0.8,
        "build_complexity": 0.3,
    }


def test_search_observations_do_not_become_scores():
    result = build_factory_intake(candidate(), research())
    assert result["factory_ready"] is False
    assert "buyer_intent_normalized_score_required" in result["blockers"]
    assert result["score_inference_from_search_results"] is False
    assert result["assessment"] is None
    assert result["revenue_verified"] is False


def test_explicit_normalized_signals_can_reach_factory():
    result = build_factory_intake(
        candidate(),
        research(),
        normalized_signals=normalized(),
    )
    assert result["factory_ready"] is True
    assert result["blockers"] == []
    assert result["assessment"]["decision"] == "build_smallest_useful_mvp"
    assert result["assessment"]["revenue_verified"] is False
    assert result["execution_authority"] == "none"


def test_batch_without_normalizers_remains_blocked():
    result = build_factory_intake_batch(
        {"candidates": [candidate()]},
        {"actions": [research()]},
    )
    assert result["candidate_count"] == 1
    assert result["factory_ready_count"] == 0
    assert result["blocked_count"] == 1
    assert result["search_observation_scores_inferred"] is False


def test_batch_accepts_evidence_normalizer_output():
    normalized_batch = {
        "items": [{
            "opportunity_key": "storm-dfw-roofing",
            "normalized_score_count": 8,
            "missing_normalized_fields": [],
            "score_evidence": {
                "demand": {
                    "value": 0.8,
                    "semantic_class": "observed_stage",
                },
            },
            "search_result_counts_used_as_scores": False,
            "normalized_signals": normalized(),
        }]
    }
    result = build_factory_intake_batch(
        {"candidates": [candidate()]},
        {"actions": [research()]},
        normalized_batch,
    )
    assert result["candidate_count"] == 1
    assert result["factory_ready_count"] == 1
    assert result["blocked_count"] == 0
    item = result["items"][0]
    assert item["normalization"]["available"] is True
    assert item["normalization"]["normalized_score_count"] == 8
    assert item["normalization"][
        "search_result_counts_used_as_scores"
    ] is False



def test_reported_normalized_count_cannot_forge_observed_scored_candidates():
    result = build_factory_intake_batch(
        {"candidates": [candidate()]},
        {"actions": [research()]},
        {"items": [{
            "opportunity_key": "storm-dfw-roofing",
            "normalized_score_count": 8,
            "normalized_signals": {"buyer_intent": None, "demand": None},
        }]},
    )
    assert result["normalized_signal_source_available"] is True
    assert result["candidates_with_any_normalized_score"] == 0
    assert result["populated_scores_computed_from_values"] is True
    assert result["candidates_with_both_buyer_intent_and_demand_values"] == 0
    assert result["candidate_evidence_gap_counts"]["buyer_intent_normalized_score_required"] == 1
    assert result["factory_ready_count"] == 0
    assert result["unverified_buyer_demand_not_negative_evidence"] is True


def test_commercial_observation_scores_are_counted_from_parsed_values():
    result = build_factory_intake_batch(
        {"candidates": [candidate()]},
        {"actions": [research()]},
        {"items": [{
            "opportunity_key": "storm-dfw-roofing",
            "normalized_score_count": 0,
            "normalized_signals": normalized(),
        }]},
    )
    assert result["factory_ready_count"] == 1
    assert result["candidates_with_any_normalized_score"] == 1
    assert result["candidates_with_both_buyer_intent_and_demand_values"] == 1
    assert result["candidate_evidence_gap_counts"] == {}
