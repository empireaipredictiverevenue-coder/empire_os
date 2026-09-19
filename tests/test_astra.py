from empire_os.astra import (
    AstraSnapshot,
    build_operating_board,
    decide,
    decide_with_outcomes,
    route_intelligence,
)


def test_astra_prioritises_live_buyer_replies():
    decision = decide(AstraSnapshot(
        replies_waiting=2,
        active_buyer_capacity=0,
        buyer_candidates_due=10,
        outbound_domain_verified=True,
    ))
    assert decision.workstream == "buyer_relationships"
    assert decision.recommended_job_type == "triage_buyer_replies"
    assert decision.intelligence_route == "local"


def test_astra_treats_zero_buyer_capacity_as_bottleneck():
    decision = decide(AstraSnapshot(
        owned_inventory_count=100,
        qualified_unallocated_count=20,
        active_buyer_capacity=0,
        buyer_candidates_due=4,
        outbound_domain_verified=True,
    ))
    assert decision.workstream == "buyer_acquisition"
    assert decision.recommended_job_type == "prepare_buyer_outreach"
    assert decision.side_effect_approval_required is True


def test_astra_blocks_outreach_priority_when_domain_is_unverified():
    decision = decide(AstraSnapshot(
        active_buyer_capacity=0,
        buyer_candidates_due=4,
        outbound_domain_verified=False,
    ))
    assert decision.recommended_job_type == "repair_outbound_channel"
    assert "outbound_domain_unverified" in decision.blockers


def test_astra_allocates_only_when_capacity_and_inventory_exist():
    decision = decide(AstraSnapshot(
        active_buyer_capacity=5,
        owned_inventory_count=10,
        qualified_unallocated_count=3,
        outbound_domain_verified=True,
    ))
    assert decision.workstream == "buyer_allocation"
    assert decision.recommended_job_type == "plan_controlled_allocation"
    assert decision.side_effect_approval_required is True


def test_astra_qualifies_owned_inventory_before_more_acquisition():
    decision = decide(AstraSnapshot(
        active_buyer_capacity=5,
        owned_inventory_count=8,
        qualified_unallocated_count=0,
        outbound_domain_verified=True,
    ))
    assert decision.workstream == "qualification"


def test_astra_never_uses_premium_ai_before_revenue():
    snapshot = AstraSnapshot(
        actual_revenue_cents=0,
        premium_ai_budget_cents=5000,
    )
    assert route_intelligence(
        snapshot,
        task_kind="deep_reasoning",
        expected_value_cents=100000,
        premium_cost_cents=100,
    ) == "local"


def test_astra_requires_premium_ai_to_clear_budget_and_roi_hurdle():
    snapshot = AstraSnapshot(
        actual_revenue_cents=100000,
        premium_ai_budget_cents=1000,
    )
    assert route_intelligence(
        snapshot,
        task_kind="deep_reasoning",
        expected_value_cents=499,
        premium_cost_cents=100,
    ) == "local"
    assert route_intelligence(
        snapshot,
        task_kind="deep_reasoning",
        expected_value_cents=500,
        premium_cost_cents=100,
    ) == "premium"


def test_astra_fails_closed_if_execution_is_unexpectedly_live():
    decision = decide(AstraSnapshot(execution_mode="live"))
    assert decision.workstream == "governance"
    assert decision.owner == "human"
    assert decision.side_effect_approval_required is True
    assert "unexpected_execution_mode" in decision.blockers


def test_verified_negative_margin_outcome_prioritises_review_not_execution():
    decision = decide_with_outcomes(
        AstraSnapshot(
            active_buyer_capacity=5,
            owned_inventory_count=10,
            outbound_domain_verified=True,
        ),
        negative_margin_orders=2,
        calibration_ready=False,
        gross_margin_rate=-0.1,
    )
    assert decision.workstream == "unit_economics"
    assert decision.recommended_job_type == "review_negative_margin"
    assert decision.owner == "revenue_intelligence"
    assert decision.side_effect_approval_required is False
    assert decision.intelligence_route == "rules"
    assert "retuning" in " ".join(decision.rationale)



def test_operating_board_ranks_multiple_observed_workstreams():
    board = build_operating_board(AstraSnapshot(
        replies_waiting=2,
        failed_jobs=1,
        active_buyer_capacity=0,
        buyer_candidates_due=4,
        outbound_domain_verified=True,
        owned_inventory_count=10,
        qualified_unallocated_count=3,
        source_health_ok=False,
    ))
    assert [item.priority for item in board.items] == sorted(
        [item.priority for item in board.items],
        reverse=True,
    )
    assert board.primary.recommended_job_type == "recover_failed_jobs"
    assert [item.recommended_job_type for item in board.items] == [
        "recover_failed_jobs",
        "triage_buyer_replies",
        "prepare_buyer_outreach",
        "qualify_owned_inventory",
        "repair_real_data_sources",
    ]
    assert board.as_dict()["side_effects"] == "none"


def test_operating_board_preserves_approval_boundaries():
    board = build_operating_board(AstraSnapshot(
        active_buyer_capacity=3,
        owned_inventory_count=8,
        qualified_unallocated_count=2,
        outbound_domain_verified=True,
    ))
    by_job = {
        item.recommended_job_type: item
        for item in board.items
    }
    assert by_job["plan_controlled_allocation"].side_effect_approval_required is True
    assert by_job["qualify_owned_inventory"].side_effect_approval_required is False


def test_operating_board_negative_margin_review_outranks_scaling():
    board = build_operating_board(
        AstraSnapshot(
            active_buyer_capacity=3,
            owned_inventory_count=8,
            qualified_unallocated_count=2,
            outbound_domain_verified=True,
        ),
        negative_margin_orders=1,
        calibration_ready=False,
        gross_margin_rate=-0.2,
    )
    assert board.primary.recommended_job_type == "review_negative_margin"
    assert board.primary.priority == 99
    assert board.items[1].recommended_job_type == "plan_controlled_allocation"


def test_operating_board_unexpected_execution_mode_is_governance_only():
    board = build_operating_board(AstraSnapshot(
        execution_mode="live",
        failed_jobs=5,
        replies_waiting=5,
    ))
    assert len(board.items) == 1
    assert board.primary.workstream == "governance"
    assert board.primary.side_effect_approval_required is True
