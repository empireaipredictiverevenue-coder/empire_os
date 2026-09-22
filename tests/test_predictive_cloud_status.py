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
