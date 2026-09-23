from datetime import datetime, timezone
import json

from empire_os.predictive_cloud_status import build_predictive_cloud_status


def write_json(root, relative, payload):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def test_status_preserves_missing_components_as_unavailable(tmp_path):
    result = build_predictive_cloud_status(
        tmp_path,
        now=datetime(2026, 9, 22, 21, 0, tzinfo=timezone.utc),
    )
    assert result["available_component_count"] == 0
    assert "revenue_pulse" in result["unavailable_components"]
    assert result["execution_authority"] == "none"


def test_status_reports_fresh_and_stale_without_inventing_health(tmp_path):
    write_json(
        tmp_path,
        "runtime/revenue_pulse/latest.json",
        {
            "generated_at": "2026-09-22T20:55:00+00:00",
            "pulse_state": "conversation_blocked",
            "highest_priority_blocker": "buyer_conversation",
            "recognized_revenue_truth": {
                "recognized_revenue_cents": 0,
                "realized_gp_cents": 0,
            },
        },
    )
    write_json(
        tmp_path,
        "runtime/market_sweeps/revenue_gps_latest.json",
        {
            "generated_at": "2026-09-22T15:00:00+00:00",
            "market_count": 4,
            "research_queue": [],
        },
    )
    result = build_predictive_cloud_status(
        tmp_path,
        now=datetime(2026, 9, 22, 21, 0, tzinfo=timezone.utc),
    )
    assert result["components"]["revenue_pulse"]["freshness"] == "fresh"
    assert result["components"]["market_gps"]["freshness"] == "stale"
    assert (
        result["components"]["revenue_pulse"]["summary"]
        ["recognized_revenue_cents"]
        == 0
    )
    assert result["revenue_recognized_by_status"] is False


def test_status_exposes_opportunity_normalization_progress(tmp_path):
    write_json(
        tmp_path,
        "runtime/opportunity_factory/normalized_signals_latest.json",
        {
            "generated_at": "2026-09-22T20:58:00+00:00",
            "candidate_count": 24,
            "candidates_with_any_normalized_score": 4,
            "total_normalized_scores": 13,
            "search_result_counts_used_as_scores": False,
        },
    )
    result = build_predictive_cloud_status(
        tmp_path,
        now=datetime(2026, 9, 22, 21, 0, tzinfo=timezone.utc),
    )
    summary = result["components"]["opportunity_normalizer"]["summary"]
    assert summary["candidate_count"] == 24
    assert summary["candidates_with_any_normalized_score"] == 4
    assert summary["total_normalized_scores"] == 13
    assert summary["search_result_counts_used_as_scores"] is False


def test_status_exposes_astra_executive_goal_and_plan(tmp_path):
    write_json(
        tmp_path,
        "runtime/astra/executive_latest.json",
        {
            "generated_at": "2026-09-22T20:59:00+00:00",
            "plan_id": "astra_plan_test",
            "primary_goal": {
                "key": "advance_first_verified_revenue",
                "priority": 98,
            },
            "plan_step_count": 4,
            "auto_dispatch_eligible_count": 3,
            "founder_gate_step_count": 1,
            "external_execution_performed": False,
            "execution_authority": "none",
        },
    )
    result = build_predictive_cloud_status(
        tmp_path,
        now=datetime(2026, 9, 22, 21, 0, tzinfo=timezone.utc),
    )
    summary = result["components"]["astra_executive"]["summary"]
    assert summary["primary_goal"] == "advance_first_verified_revenue"
    assert summary["plan_step_count"] == 4
    assert summary["auto_dispatch_eligible_count"] == 3
    assert summary["founder_gate_step_count"] == 1
    assert summary["external_execution_performed"] is False


def test_status_exposes_quant_review_and_department_coverage(tmp_path):
    write_json(
        tmp_path,
        "runtime/opportunity_factory/quant_review_latest.json",
        {
            "generated_at": "2026-09-22T20:59:00+00:00",
            "candidate_count": 24,
            "available_decision_packet_count": 2,
            "unavailable_decision_packet_count": 22,
            "missing_field_counts": {
                "probability_success": 22,
            },
            "capital_execution": False,
            "execution_authority": "none",
        },
    )
    result = build_predictive_cloud_status(
        tmp_path,
        now=datetime(2026, 9, 22, 21, 0, tzinfo=timezone.utc),
    )
    summary = result["components"]["opportunity_quant_review"]["summary"]
    assert summary["available_decision_packet_count"] == 2
    assert summary["unavailable_decision_packet_count"] == 22
    assert summary["capital_execution"] is False

    organization = result["organization"]
    assert organization["department_count"] >= 10
    assert organization["all_department_components_registered"] is True
    assert organization["fully_wired_department_count"] == organization[
        "department_count"
    ]


def test_status_exposes_verified_predictive_intelligence(tmp_path):
    write_json(
        tmp_path,
        "runtime/predictive_intelligence/latest.json",
        {
            "generated_at": "2026-09-22T20:59:00+00:00",
            "source_outcome_count": 30,
            "matched_outcome_count": 25,
            "probability_ready_product_count": 1,
            "timing_ready_product_count": 0,
            "minimum_terminal_samples": 20,
            "minimum_timing_samples": 8,
            "search_scores_used": False,
            "llm_probability_used": False,
            "execution_authority": "none",
        },
    )
    result = build_predictive_cloud_status(
        tmp_path,
        now=datetime(2026, 9, 22, 21, 0, tzinfo=timezone.utc),
    )
    summary = result["components"]["predictive_intelligence"]["summary"]
    assert summary["source_outcome_count"] == 30
    assert summary["probability_ready_product_count"] == 1
    assert summary["search_scores_used"] is False
    assert summary["llm_probability_used"] is False


def test_status_exposes_economic_memory_without_promoting_outcomes(tmp_path):
    write_json(
        tmp_path,
        "runtime/economic_memory/latest.json",
        {
            "generated_at": "2026-09-22T20:58:00+00:00",
            "plan_id": "astra_plan_test",
            "plan_evaluation_state": "BLOCKED",
            "department_episode_count": 8,
            "outcome_conditioned_memory_count": 0,
            "rejected_outcome_memory_count": 0,
            "verified_outcomes_only_for_outcome_conditioned_memory": True,
            "model_weight_mutation_authorized": False,
            "execution_authority": "none",
        },
    )
    result = build_predictive_cloud_status(
        tmp_path,
        now=datetime(2026, 9, 22, 21, 0, tzinfo=timezone.utc),
    )
    row = result["components"]["economic_memory"]
    assert row["available"] is True
    assert row["freshness"] == "fresh"
    assert row["summary"]["department_episode_count"] == 8
    assert row["summary"]["outcome_conditioned_memory_count"] == 0
    assert row["summary"]["verified_outcomes_only"] is True
    assert row["summary"]["model_weight_mutation_authorized"] is False
    assert row["execution_authority"] == "none"


def test_status_exposes_opportunity_value_without_claiming_revenue(tmp_path):
    write_json(
        tmp_path,
        "runtime/opportunity_factory/value_latest.json",
        {
            "generated_at": "2026-09-22T20:59:00+00:00",
            "candidate_count": 3,
            "value_available_count": 1,
            "value_unavailable_count": 2,
            "items": [{
                "opportunity_key": "opp-1",
                "status": "AVAILABLE",
                "rank": 1,
                "risk_adjusted_score": 42000.0,
            }],
            "new_scoring_model_introduced": False,
            "prediction_only": True,
            "actual_revenue": False,
            "execution_authority": "none",
        },
    )
    result = build_predictive_cloud_status(
        tmp_path,
        now=datetime(2026, 9, 22, 21, 0, tzinfo=timezone.utc),
    )
    row = result["components"]["opportunity_value"]
    summary = row["summary"]

    assert row["available"] is True
    assert row["freshness"] == "fresh"
    assert summary["value_available_count"] == 1
    assert summary["value_unavailable_count"] == 2
    assert summary["top_opportunity_key"] == "opp-1"
    assert summary["top_risk_adjusted_score"] == 42000.0
    assert summary["new_scoring_model_introduced"] is False
    assert summary["prediction_only"] is True
    assert row["execution_authority"] == "none"


def test_status_exposes_commercial_exchange_without_external_authority(tmp_path):
    write_json(
        tmp_path,
        "runtime/commercial_exchange/latest.json",
        {
            "observed_at": "2026-09-23T00:00:00+00:00",
            "inventory_count": 7,
            "allocation_candidate_count": 2,
            "overflow_count": 5,
            "buyer_seat_count": 3,
            "corridor_count": 2,
            "buyer_capacity_never_gates_acquisition": True,
            "overflow_remains_empire_owned": True,
            "automatic_external_delivery": False,
            "seat_activation_blocker_counts": {
                "buyer_not_commercially_activated": 3,
            },
            "supply_gate_diagnostics": {
                "prospects_seen": 7,
                "qualification_ready_count": 2,
                "exchange_inventory_ready_count": 2,
            },
            "execution_authority": "none",
        },
    )

    result = build_predictive_cloud_status(
        tmp_path,
        now=datetime.fromisoformat("2026-09-23T00:05:00+00:00"),
    )
    component = result["components"]["commercial_exchange"]

    assert component["available"] is True
    assert component["summary"]["inventory_count"] == 7
    assert component["summary"]["overflow_count"] == 5
    assert component["summary"][
        "buyer_capacity_never_gates_acquisition"
    ] is True
    assert component["summary"]["overflow_remains_empire_owned"] is True
    assert component["summary"]["automatic_external_delivery"] is False
    assert component["summary"]["seat_activation_blocker_counts"] == {
        "buyer_not_commercially_activated": 3
    }
    assert component["summary"]["supply_gate_diagnostics"][
        "qualification_ready_count"
    ] == 2


def test_status_exposes_buyer_acquisition_team_without_live_send(tmp_path):
    write_json(
        tmp_path,
        "runtime/buyer_acquisition/latest.json",
        {
            "generated_at": "2026-09-23T00:15:00+00:00",
            "team_role_count": 10,
            "buyer_pools": [
                {"pool": "local_and_smb_buyers"},
                {"pool": "direct_demand_buyers"},
                {"pool": "enterprise_and_data_buyers"},
            ],
            "demand_gap_count": 5,
            "priority_targets": [{}, {}, {}],
            "product_demand_count": 8,
            "sellable_product_demand_count": 1,
            "market_validate_product_count": 7,
            "automation": {
                "live_outbound_send": False,
            },
            "canonical_settlement_rail": "USDT_BSC",
            "buyer_capacity_never_gates_acquisition": True,
            "execution_authority": "none",
        },
    )

    result = build_predictive_cloud_status(
        tmp_path,
        now=datetime.fromisoformat("2026-09-23T00:20:00+00:00"),
    )
    component = result["components"]["buyer_acquisition_team"]

    assert component["available"] is True
    assert component["freshness"] == "fresh"
    assert component["summary"]["team_role_count"] == 10
    assert component["summary"]["buyer_pool_count"] == 3
    assert component["summary"]["demand_gap_count"] == 5
    assert component["summary"]["product_demand_count"] == 8
    assert component["summary"]["sellable_product_demand_count"] == 1
    assert component["summary"]["market_validate_product_count"] == 7
    assert component["summary"]["live_outbound_send"] is False
    assert component["summary"]["canonical_settlement_rail"] == "USDT_BSC"
    assert component["execution_authority"] == "none"



def test_status_exposes_tag_intelligence_without_mutation_authority(tmp_path):
    write_json(
        tmp_path,
        "runtime/tag_intelligence/latest.json",
        {
            "mode": "OBSERVE",
            "generated_at": "2026-09-23T09:00:00+00:00",
            "target_count": 4,
            "available_target_count": 4,
            "failed_target_count": 0,
            "critical_issue_count": 1,
            "high_issue_count": 3,
            "search_issue_count": 5,
            "measurement_issue_count": 4,
            "change_count": 6,
            "critical_change_count": 2,
            "monitored_site_count": 3,
            "monitored_page_count": 4,
            "pages_with_public_noindex": 1,
            "pages_missing_canonical": 1,
            "pages_missing_schema": 2,
            "missing_conversion_event_count": 1,
            "duplicate_conversion_event_count": 1,
            "measurement_observation": {
                "ga4": "OBSERVED_IN_STATIC_MARKUP",
                "revenue_truth_linkage": "UNKNOWN",
            },
            "automatic_tag_mutation": False,
            "measurement_platform_write": False,
            "execution_authority": "none",
        },
    )

    result = build_predictive_cloud_status(
        tmp_path,
        now=datetime(
            2026, 9, 23, 10, 0, tzinfo=timezone.utc
        ),
    )
    component = result["components"]["tag_intelligence"]

    assert component["available"] is True
    assert component["summary"]["target_count"] == 4
    assert component["summary"]["critical_issue_count"] == 1
    assert component["summary"]["search_issue_count"] == 5
    assert component["summary"]["measurement_issue_count"] == 4
    assert component["summary"]["change_count"] == 6
    assert component["summary"]["critical_change_count"] == 2
    assert component["summary"]["monitored_site_count"] == 3
    assert component["summary"]["monitored_page_count"] == 4
    assert component["summary"]["pages_with_public_noindex"] == 1
    assert component["summary"]["pages_missing_canonical"] == 1
    assert component["summary"]["pages_missing_schema"] == 2
    assert component["summary"]["measurement_observation"]["ga4"] == (
        "OBSERVED_IN_STATIC_MARKUP"
    )
    assert component["summary"]["automatic_tag_mutation"] is False
    assert component["summary"]["measurement_platform_write"] is False
    assert component["execution_authority"] == "none"


def test_status_exposes_icp_buyer_trigger_intelligence(tmp_path):
    write_json(
        tmp_path,
        "runtime/buyer_acquisition/latest.json",
        {
            "generated_at": "2026-09-23T12:00:00+00:00",
            "team_role_count": 11,
            "buyer_pools": [{"pool": "enterprise_and_data_buyers"}],
            "demand_gap_count": 1,
            "priority_targets": [{}],
            "product_demand_count": 4,
            "sellable_product_demand_count": 1,
            "market_validate_product_count": 3,
            "icp_priority_target_count": 6,
            "icp_buyer_trigger_intelligence": {
                "profile_count": 6,
                "execution_authority": "none",
            },
            "automation": {"live_outbound_send": False},
            "canonical_settlement_rail": "USDT_BSC",
            "buyer_capacity_never_gates_acquisition": True,
            "execution_authority": "none",
        },
    )

    result = build_predictive_cloud_status(
        tmp_path,
        now=datetime.fromisoformat("2026-09-23T12:05:00+00:00"),
    )
    summary = result["components"]["buyer_acquisition_team"]["summary"]

    assert summary["icp_priority_target_count"] == 6
    assert summary["icp_profile_count"] == 6
    assert summary["icp_execution_authority"] == "none"
    assert summary["live_outbound_send"] is False


def test_status_exposes_buyer_scout_icp_evidence_counts(tmp_path):
    write_json(
        tmp_path,
        "runtime/buyer_acquisition/scout_latest.json",
        {
            "generated_at": "2026-09-23T12:10:00+00:00",
            "query_count": 12,
            "domain_count": 8,
            "candidate_count": 4,
            "explicit_direct_buyer_candidate_count": 1,
            "icp_assessed_candidate_count": 4,
            "observed_trigger_candidate_count": 2,
            "decision_maker_role_match_count": 2,
            "economic_capacity_proxy_count": 1,
            "verified_budget_candidate_count": 0,
            "database_write_performed": False,
            "outbound_sent": False,
            "execution_authority": "none",
        },
    )

    result = build_predictive_cloud_status(
        tmp_path,
        now=datetime.fromisoformat("2026-09-23T12:15:00+00:00"),
    )
    summary = result["components"]["buyer_acquisition_scout"]["summary"]

    assert summary["icp_assessed_candidate_count"] == 4
    assert summary["observed_trigger_candidate_count"] == 2
    assert summary["decision_maker_role_match_count"] == 2
    assert summary["economic_capacity_proxy_count"] == 1
    assert summary["verified_budget_candidate_count"] == 0
    assert summary["outbound_sent"] is False


def test_status_exposes_media_os_runtime_without_external_authority(tmp_path):
    write_json(
        tmp_path,
        "runtime/media_os/latest.json",
        {
            "generated_at": "2026-09-23T13:30:00+00:00",
            "mode": "OBSERVE",
            "runtime_active": True,
            "real_evidence_present": True,
            "observed_source_count": 4,
            "youtube_public": {
                "observation_count": 12,
                "outliers": {
                    "candidate_count": 3,
                },
            },
            "algorithm_intelligence": {
                "observation_count": 8,
                "hypothesis_count": 4,
            },
            "trend_fusion": {
                "topic_count": 5,
            },
            "idea_backlog": {
                "candidate_count": 9,
                "pending_quant_review_count": 9,
            },
            "ready_for_research_generation": True,
            "public_publish_authorized": False,
            "external_action_performed": False,
            "execution_authority": "none",
        },
    )

    result = build_predictive_cloud_status(
        tmp_path,
        now=datetime(2026, 9, 23, 13, 45, tzinfo=timezone.utc),
    )

    row = result["components"]["media_os"]
    summary = row["summary"]

    assert row["available"] is True
    assert row["freshness"] == "fresh"
    assert summary["runtime_active"] is True
    assert summary["real_evidence_present"] is True
    assert summary["observed_source_count"] == 4
    assert summary["youtube_observation_count"] == 12
    assert summary["outlier_candidate_count"] == 3
    assert summary["algorithm_observation_count"] == 8
    assert summary["algorithm_hypothesis_count"] == 4
    assert summary["trend_topic_count"] == 5
    assert summary["idea_candidate_count"] == 9
    assert summary["pending_quant_review_count"] == 9
    assert summary["ready_for_research_generation"] is True
    assert summary["public_publish_authorized"] is False
    assert summary["external_action_performed"] is False
    assert row["execution_authority"] == "none"
