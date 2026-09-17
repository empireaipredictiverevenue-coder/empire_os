from empire_os.astra import AstraSnapshot, decide, route_intelligence


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
