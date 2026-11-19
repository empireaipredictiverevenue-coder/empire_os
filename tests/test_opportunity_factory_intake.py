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


def trusted_normalizer_batch():
    from datetime import datetime, timezone
    from empire_os.opportunity_factory_intake import SCORE_KEYS
    values = normalized()
    evidence = {}
    sources = {
        "buyer_intent": "canonical:outbound_replies:commercial",
        "demand": "canonical:outbound_replies:commercial",
        "urgency": "canonical:sensor_mesh:observed_event",
        "margin_potential": "canonical:commercial_product_catalog",
        "distribution_strength": "canonical:buyer_candidate_reviews",
        "data_advantage": "canonical:source_coverage",
        "fulfilment_readiness": "canonical:fulfilment_orders",
        "build_complexity": "canonical:commercial_product_catalog",
    }
    for key in SCORE_KEYS:
        semantic = "observed_stage" if key in ("buyer_intent", "demand") else "modeled_proxy"
        evidence[key] = {
            "value": values[key], "semantic_class": semantic,
            "basis": f"fixture_{key}_observed_basis",
            "evidence_refs": [sources[key]],
            "observed_truth": semantic == "observed_stage",
            "modeled_or_policy": semantic == "modeled_proxy",
        }
    return {
        "schema_version": "empire.opportunity_evidence_normalizer_batch.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "OBSERVE", "execution_authority": "none",
        "candidate_count": 1,
        "search_result_counts_used_as_scores": False,
        "market_share_inferred": False, "revenue_inferred": False,
        "items": [{
            "schema_version": "empire.opportunity_evidence_normalizer.v1",
            "mode": "OBSERVE", "execution_authority": "none",
            "opportunity_key": "storm-dfw-roofing",
            "opportunity_class": "event_market",
            "normalized_score_count": 8,
            "normalized_signals": values,
            "score_evidence": evidence,
            "search_result_counts_used_as_scores": False,
            "competitor_gaps_used_as_demand": False,
            "buyer_intent_inferred_from_public_pain": False,
            "market_share_inferred": False, "revenue_inferred": False,
        }],
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
    normalized_batch = trusted_normalizer_batch()
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
    value = trusted_normalizer_batch()
    value["items"][0]["normalized_score_count"] = 0
    result = build_factory_intake_batch(
        {"candidates": [candidate()]},
        {"actions": [research()]}, value,
    )
    assert result["factory_ready_count"] == 0
    assert result["candidates_with_any_normalized_score"] == 0
    assert result["candidates_with_both_buyer_intent_and_demand_values"] == 0
    assert result["normalizer_rows_rejected_for_evidence"] == 1
    assert result["items"][0]["normalization"]["score_evidence"] == {}


def test_complete_numeric_values_without_evidence_never_mark_factory_ready():
    forged = trusted_normalizer_batch()
    forged["items"][0]["score_evidence"] = {}
    result = build_factory_intake_batch(
        {"candidates": [candidate()]}, {"actions": [research()]},
        forged,
    )
    assert result["factory_ready_count"] == 0
    assert result["items"][0]["assessment"] is None
    assert result["items"][0]["normalization"]["score_evidence"] == {}
    assert result["normalizer_rows_rejected_for_evidence"] == 1
    assert result["execution_authority"] == "none"


def test_valid_evidence_binding_accepts_complete_scored_internal_fixture():
    from empire_os.opportunity_evidence_router import build_evidence_routes
    forged = trusted_normalizer_batch()
    normalized_data = build_factory_intake_batch(
        {"candidates": [candidate()]}, {"actions": [research()]},
        forged,
    )
    assert normalized_data["factory_ready_count"] == 1
    assert normalized_data["normalizer_rows_rejected_for_evidence"] == 0
    assert normalized_data["items"][0]["normalization"]["normalized_score_count"] == 8
    assert normalized_data["execution_authority"] == "none"
    # Fixture readiness is NOT a live purchase or a buyer acceptance.
    assert normalized_data["items"][0]["revenue_verified"] is False
    assert normalized_data["items"][0]["normalization"]["available"] is True


def test_duplicate_normalizer_identity_cannot_promote_either_record():
    forged = trusted_normalizer_batch()
    forged["items"].append(dict(forged["items"][0]))
    forged["candidate_count"] = 2
    result = build_factory_intake_batch(
        {"candidates": [candidate()]}, {"actions": [research()]},
        forged,
    )
    assert result["factory_ready_count"] == 0
    assert result["normalizer_batch_contract_accepted"] is False
    assert result["items"][0]["normalization"]["score_evidence"] == {}


def test_forged_observed_truth_value_is_not_lifecycle_validation():
    from empire_os.opportunity_evidence_router import build_evidence_routes
    forged = trusted_normalizer_batch()
    forged["items"][0]["score_evidence"]["buyer_intent"]["observed_truth"] = False
    result = build_factory_intake_batch(
        {"candidates": [candidate()]}, {"actions": [research()]}, forged,
    )
    assert result["factory_ready_count"] == 0
    assert result["items"][0]["normalization"]["score_evidence"] == {}
    assert result["normalizer_rows_rejected_for_evidence"] == 1


def test_expired_or_future_normalizer_snapshot_cannot_promote_candidate():
    from datetime import datetime, timezone, timedelta
    clock = datetime.now(timezone.utc)
    for stamp in (
        clock-timedelta(days=1),
        clock+timedelta(minutes=6),
    ):
        supplied = trusted_normalizer_batch()
        supplied["generated_at"] = stamp.isoformat()
        result = build_factory_intake_batch(
            {"candidates": [candidate()]}, {"actions": [research()]},
            supplied, now=clock,
        )
        assert result["factory_ready_count"] == 0
        assert result["normalizer_batch_contract_accepted"] is False
        assert result["items"][0]["normalization"]["score_evidence"] == {}
        assert result["execution_authority"] == "none"


def test_evidence_bound_factory_to_router_to_astra_existing_owner_lane():
    from datetime import datetime, timezone
    from empire_os.opportunity_evidence_router import build_evidence_routes
    from empire_os.opportunity_history import build_opportunity_history
    from empire_os.astra_validated_workstream_ranking import rank_validated_workstreams

    valid = trusted_normalizer_batch()
    row = valid["items"][0]
    # Partial real-world inputs may validate an observed commercial stage
    # while keeping further research blockers and commercial gates intact.
    row["normalized_signals"]["urgency"] = None
    row["score_evidence"].pop("urgency")
    row["normalized_score_count"] = 7
    radar = {"candidates": [candidate()]}
    intake = build_factory_intake_batch(
        radar, {"actions": [research()]}, valid,
    )
    assert intake["factory_ready_count"] == 0
    assert intake["items"][0]["normalization"]["available"] is True
    assert intake["items"][0]["normalization"]["score_evidence"]["buyer_intent"]["observed_truth"] is True
    routes = build_evidence_routes(radar, intake)
    assert routes["stage_counts"] == {"VALIDATE": 1}
    assert any(r["blocker"] == "urgency_normalized_score_required"
               for r in routes["items"][0]["routes"])
    routes["history"] = build_opportunity_history(routes, None)
    clock = datetime.fromisoformat(routes["generated_at"])
    ranked = rank_validated_workstreams(
        routes,
        capability_components={"sensor_mesh": "sensor_mesh"},
        component_authorities={"sensor_mesh": "observe"},
        department_owners={"sensor_mesh": ("data_quant",)},
        now=clock,
    )
    assert ranked["status"] == "RANKED_FROM_CURRENT_DERIVED_VALIDATION"
    assert ranked["validated_opportunity_count"] == 1
    assert ranked["ranked_workstream_count"] == 1
    assert ranked["workstreams"][0]["department_keys"] == ["data_quant"]
    assert ranked["automatic_external_execution_allowed"] is False
    assert ranked["source_validation_is_not_buyer_acceptance"] is True
    assert ranked["execution_authority"] == "none"


def test_unsupported_factory_scores_never_become_astra_validated_workstreams():
    from datetime import datetime
    from empire_os.opportunity_evidence_router import build_evidence_routes
    from empire_os.opportunity_history import build_opportunity_history
    from empire_os.astra_validated_workstream_ranking import rank_validated_workstreams
    forged = trusted_normalizer_batch()
    forged["items"][0]["score_evidence"]["buyer_intent"]["observed_truth"] = False
    radar = {"candidates": [candidate()]}
    intake = build_factory_intake_batch(radar, {"actions": [research()]}, forged)
    assert intake["normalizer_rows_rejected_for_evidence"] == 1
    assert intake["factory_ready_count"] == 0
    routes = build_evidence_routes(radar, intake)
    assert routes["stage_counts"].get("VALIDATE", 0) == 0
    routes["history"] = build_opportunity_history(routes, None)
    ranked = rank_validated_workstreams(
        routes,
        capability_components={"sensor_mesh": "sensor_mesh"},
        component_authorities={"sensor_mesh": "observe"},
        department_owners={"sensor_mesh": ("data_quant",)},
        now=datetime.fromisoformat(routes["generated_at"]),
    )
    assert ranked["validated_opportunity_count"] == 0
    assert ranked["ranked_workstream_count"] == 0
    assert ranked["automatic_external_execution_allowed"] is False
