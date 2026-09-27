from pathlib import Path

from empire_os.opportunity_loop import run_opportunity_loop


def test_opportunity_loop_runs_in_order_and_stays_noncommercial(tmp_path):
    calls = []

    def radar(root: Path):
        calls.append(("radar", root))
        return {"candidate_count": 3}

    def research(root: Path):
        calls.append(("research", root))
        return {
            "researched_candidate_count": 2,
            "observation_count": 5,
            "error_count": 0,
        }

    def normalizer(root: Path):
        calls.append(("normalizer", root))
        return {
            "candidates_with_any_normalized_score": 2,
            "total_normalized_scores": 7,
        }

    def intake(root: Path):
        calls.append(("intake", root))
        return {
            "candidate_count": 3,
            "factory_ready_count": 0,
            "blocked_count": 3,
        }

    def quant(root: Path):
        calls.append(("quant", root))
        return {
            "available_decision_packet_count": 0,
            "unavailable_decision_packet_count": 3,
            "missing_field_counts": {"probability_success": 3},
        }

    def value(root: Path):
        calls.append(("value", root))
        return {
            "value_available_count": 0,
            "value_unavailable_count": 3,
        }

    def router(root: Path):
        calls.append(("router", root))
        return {
            "stage_counts": {"QUALIFY": 3},
            "automatic_internal_route_count": 4,
            "commercial_observation_route_count": 2,
        }

    def planner(root: Path, *, limit: int):
        calls.append(("planner", root, limit))
        return {
            "queued_count": 2,
            "skipped_unchanged": 1,
        }

    result = run_opportunity_loop(
        tmp_path,
        force=True,
        radar_fn=radar,
        research_fn=research,
        normalizer_fn=normalizer,
        intake_fn=intake,
        quant_review_fn=quant,
        opportunity_value_fn=value,
        evidence_router_fn=router,
        planner_fn=planner,
    )

    assert [item[0] for item in calls] == [
        "radar",
        "research",
        "normalizer",
        "intake",
        "quant",
        "value",
        "router",
        "planner",
    ]
    assert calls[-1][2] == 3
    assert result["ok"] is True
    assert result["research_observation_count"] == 5
    assert result["candidates_with_any_normalized_score"] == 2
    assert result["total_normalized_scores"] == 7
    assert result["factory_blocked_count"] == 3
    assert result["quant_decision_packet_unavailable_count"] == 3
    assert result["quant_missing_field_counts"] == {
        "probability_success": 3
    }
    assert result["opportunity_value_available_count"] == 0
    assert result["opportunity_value_unavailable_count"] == 3
    assert result["opportunity_stage_counts"] == {"QUALIFY": 3}
    assert result["ai_plan_queued_count"] == 2
    assert result["automatic_internal_research"] is True
    assert result["automatic_evidence_normalization"] is True
    assert result["automatic_factory_intake"] is True
    assert result["automatic_quant_review"] is True
    assert result["automatic_opportunity_value_scoring"] is True
    assert result["automatic_evidence_routing"] is True
    assert result["automatic_ai_planning"] is True
    assert result["automatic_external_execution_allowed"] is False
    assert result["outreach_sent"] is False
    assert result["payment_action"] is False
    assert result["revenue_recognized"] is False
    assert result["execution_authority"] == "none"


def test_opportunity_loop_fails_closed_and_stops_on_step_error(tmp_path):
    calls = []

    def radar(_root):
        calls.append("radar")
        raise RuntimeError("radar failed")

    def should_not_run(_root, **_kwargs):
        calls.append("unexpected")
        return {}

    result = run_opportunity_loop(
        tmp_path,
        force=True,
        radar_fn=radar,
        research_fn=should_not_run,
        normalizer_fn=should_not_run,
        intake_fn=should_not_run,
        quant_review_fn=should_not_run,
        opportunity_value_fn=should_not_run,
        evidence_router_fn=should_not_run,
        planner_fn=should_not_run,
    )

    assert calls == ["radar"]
    assert result["ok"] is False
    assert result["steps"][0]["step"] == "opportunity_radar"
    assert result["automatic_external_execution_allowed"] is False


def test_opportunity_loop_freshness_guard_avoids_duplicate_work(tmp_path):
    calls = []

    def radar(_root):
        calls.append("radar")
        return {"candidate_count": 1}

    def research(_root):
        calls.append("research")
        return {
            "researched_candidate_count": 1,
            "observation_count": 1,
        }

    def normalizer(_root):
        calls.append("normalizer")
        return {
            "candidates_with_any_normalized_score": 1,
            "total_normalized_scores": 3,
        }

    def intake(_root):
        calls.append("intake")
        return {
            "factory_ready_count": 0,
            "blocked_count": 1,
        }

    def quant(_root):
        calls.append("quant")
        return {
            "available_decision_packet_count": 0,
            "unavailable_decision_packet_count": 1,
            "missing_field_counts": {"probability_success": 1},
        }

    def value(_root):
        calls.append("value")
        return {
            "value_available_count": 0,
            "value_unavailable_count": 1,
        }

    def router(_root):
        calls.append("router")
        return {
            "stage_counts": {"QUALIFY": 1},
            "automatic_internal_route_count": 1,
            "commercial_observation_route_count": 1,
        }

    def planner(_root, *, limit):
        calls.append("planner")
        return {
            "queued_count": 1,
            "skipped_unchanged": 0,
        }

    first = run_opportunity_loop(
        tmp_path,
        min_interval_seconds=1800,
        radar_fn=radar,
        research_fn=research,
        normalizer_fn=normalizer,
        intake_fn=intake,
        quant_review_fn=quant,
        opportunity_value_fn=value,
        evidence_router_fn=router,
        planner_fn=planner,
    )
    second = run_opportunity_loop(
        tmp_path,
        min_interval_seconds=1800,
        radar_fn=radar,
        research_fn=research,
        normalizer_fn=normalizer,
        intake_fn=intake,
        quant_review_fn=quant,
        opportunity_value_fn=value,
        evidence_router_fn=router,
        planner_fn=planner,
    )

    assert first["skipped_fresh"] is False
    assert second["skipped_fresh"] is True
    assert calls == [
        "radar",
        "research",
        "normalizer",
        "intake",
        "quant",
        "value",
        "router",
        "planner",
    ]
