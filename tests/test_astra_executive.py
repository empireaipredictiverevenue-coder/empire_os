from empire_os.astra_executive import (
    build_executive_snapshot,
    build_world_state,
    derive_goals,
)


def status(*, unavailable=(), stale=()):
    return {
        "available_component_count": 10,
        "unavailable_components": list(unavailable),
        "stale_components": list(stale),
    }


def pulse(*, revenue=0, blocker="buyer_conversation"):
    return {
        "pulse_state": "conversation_blocked",
        "highest_priority_blocker": blocker,
        "recognized_revenue_truth": {
            "recognized_revenue_cents": revenue,
            "realized_gp_cents": 0,
        },
    }


def routes():
    return {
        "opportunity_count": 1,
        "stage_counts": {"QUALIFY": 1},
        "items": [{
            "opportunity_key": "market:roofing:denver",
            "opportunity_class": "market_research",
            "lifecycle": {
                "current_stage": "QUALIFY",
                "next_stage": "VALIDATE",
            },
            "routes": [{
                "blocker": "fulfilment_readiness_normalized_score_required",
                "capability": "commercial_product_catalog_and_fulfilment",
                "action": "resolve_verified_fulfilment_cost_capacity_and_runbook",
                "mode": "internal_analysis",
                "automatic_internal_work": True,
            }],
        }],
    }


def nba():
    return {
        "founder_gate_count": 0,
        "waiting_external_count": 0,
        "outreach_authorized": False,
        "payment_authorized": False,
        "actions": [{
            "entity_id": "company:1",
            "company_name": "Example Co",
            "recommended_action": "verify_decision_maker",
            "reason": "ready but decision-maker unresolved",
            "founder_gate_required": False,
            "waiting_external": False,
            "evidence": {"ready_observed": True},
        }],
    }


def test_world_state_preserves_revenue_truth_and_routes():
    world = build_world_state(
        predictive_status=status(),
        evidence_routes=routes(),
        next_best_action=nba(),
        revenue_pulse=pulse(),
    )
    assert world["recognized_revenue_cents"] == 0
    assert world["revenue_blocker"] == "buyer_conversation"
    assert len(world["automatic_internal_evidence_routes"]) == 1
    assert world["execution_authority"] == "none"


def test_goals_prioritize_first_real_revenue_then_buyer_progression():
    world = build_world_state(
        predictive_status=status(),
        evidence_routes=routes(),
        next_best_action=nba(),
        revenue_pulse=pulse(),
    )
    goals = derive_goals(world)
    assert goals[0].key == "advance_first_verified_revenue"
    assert any(
        goal.key == "complete_opportunity_evidence"
        for goal in goals
    )


def test_missing_truth_outranks_revenue_work():
    world = build_world_state(
        predictive_status=status(unavailable=("source_health",)),
        evidence_routes=routes(),
        next_best_action=nba(),
        revenue_pulse=pulse(),
    )
    goals = derive_goals(world)
    assert goals[0].key == "restore_operating_truth"
    assert goals[0].priority == 100


def test_executive_delegates_to_existing_components_with_memory_scope():
    result = build_executive_snapshot(
        predictive_status=status(),
        evidence_routes=routes(),
        next_best_action=nba(),
        revenue_pulse=pulse(),
    )
    components = {
        row["target_component"] for row in result["plan"]
    }
    assert "identity_enrichment" in components
    assert "fulfilment_readiness" in components
    assert result["plan_step_count"] >= 2
    assert result["external_execution_performed"] is False
    assert result["execution_authority"] == "none"
    for row in result["plan"]:
        assert row["memory_query"]["retrieval_only"] is True
        assert row["success_condition"]


def test_founder_gate_next_action_is_never_auto_dispatch_eligible():
    gated = nba()
    gated["actions"][0] = {
        **gated["actions"][0],
        "recommended_action": "payment_review",
        "founder_gate_required": True,
    }
    result = build_executive_snapshot(
        predictive_status=status(),
        evidence_routes={},
        next_best_action=gated,
        revenue_pulse=pulse(),
    )
    payment = next(
        row for row in result["plan"]
        if row["action"] == "payment_review"
    )
    assert payment["authority"] == "founder_gate"
    assert payment["auto_dispatch_eligible"] is False
    assert payment["founder_gate_required"] is True
