from empire_os.action_portfolio_optimization import (
    build_cqm_export,
    build_portfolio_optimization_plan,
    build_portfolio_optimization_problem,
    build_qubo_export,
    optimize_action_portfolio,
    review_portfolio_benchmark,
    solve_portfolio_classical_exact,
    solve_portfolio_classical_greedy,
)


def _actions():
    return [
        {
            "action_key": "follow_up",
            "expected_incremental_value_cents": 9000,
            "action_cost_cents": 1000,
            "capacity_group": "outreach",
            "evidence_refs": ["erv:follow_up"],
        },
        {
            "action_key": "proposal",
            "expected_incremental_value_cents": 12000,
            "action_cost_cents": 3000,
            "capacity_group": "proposal",
            "evidence_refs": ["erv:proposal"],
        },
        {
            "action_key": "call",
            "expected_incremental_value_cents": 7000,
            "action_cost_cents": 1000,
            "capacity_group": "outreach",
            "evidence_refs": ["erv:call"],
        },
    ]


def _problem(budget=5000, capacities=None):
    return build_portfolio_optimization_problem(
        actions=_actions(),
        budget_cents=budget,
        capacity_constraints=capacities or {
            "outreach": 1,
            "proposal": 1,
        },
    )


def test_problem_preserves_unknown_action_economics():
    problem = build_portfolio_optimization_problem(
        actions=[
            {
                "action_key": "unknown",
                "expected_incremental_value_cents": None,
                "action_cost_cents": 100,
                "evidence_refs": ["erv:unknown"],
            },
            _actions()[0],
        ],
        budget_cents=5000,
        capacity_constraints={"outreach": 1},
    )
    assert problem["status"] == "AVAILABLE"
    assert problem["unknown_is_zero"] is False
    assert problem["blocked_actions"][0]["reason"] == (
        "unknown_action_economics_preserved"
    )


def test_exact_reference_respects_budget_and_capacity():
    result = solve_portfolio_classical_exact(_problem())
    assert result["status"] == "AVAILABLE"
    assert result["optimal_for_normalized_problem"] is True
    assert result["total_cost_cents"] <= 5000
    assert result["execution_authority"] == "none"


def test_exact_reference_respects_variable_limit():
    result = solve_portfolio_classical_exact(
        _problem(),
        max_variables=2,
    )
    assert result["status"] == "UNAVAILABLE"
    assert result["reason"] == "exact_reference_variable_limit_exceeded"


def test_greedy_is_deterministic():
    results = [
        solve_portfolio_classical_greedy(_problem())
        for _ in range(3)
    ]
    assert all(
        row["selected_actions"] == results[0]["selected_actions"]
        for row in results
    )


def test_cqm_keeps_budget_and_capacity_constraints():
    cqm = build_cqm_export(_problem())
    names = {row["name"] for row in cqm["constraints"]}
    assert cqm["status"] == "AVAILABLE"
    assert "total_budget" in names
    assert "capacity_group::outreach" in names
    assert cqm["external_solver_called"] is False


def test_qubo_is_benchmark_only():
    qubo = build_qubo_export(_problem())
    assert qubo["status"] == "AVAILABLE"
    assert qubo["model_type"] == "QUBO"
    assert qubo["qaoa_ready"] is True
    assert qubo["external_solver_called"] is False


def test_plan_never_promotes_quantum_automatically():
    plan = build_portfolio_optimization_plan(_problem())
    assert plan["status"] == "AVAILABLE"
    assert plan["primary_classical_lane"] == "classical_exact"
    assert plan["classical_reference_quality"] == "OPTIMAL_REFERENCE"
    assert plan["production_promotion_ready"] is False
    assert plan["quantum_advantage_claimed"] is False
    assert plan["portfolio_execution"] is False


def test_plan_falls_back_to_greedy_for_large_problem():
    plan = build_portfolio_optimization_plan(
        _problem(),
        exact_variable_limit=2,
    )
    assert plan["primary_classical_lane"] == "classical_greedy"
    assert plan["classical_reference_quality"] == "HEURISTIC_REFERENCE"


def test_optimize_action_portfolio_uses_predictive_nba():
    raw = [
        {
            "action_key": "follow_up",
            "probability_action_changes_outcome": 0.5,
            "incremental_revenue_if_changed_cents": 20000,
            "action_cost_cents": 1000,
            "confidence": 1.0,
            "capacity_group": "outreach",
            "evidence_refs": ["nba:follow_up"],
        },
        {
            "action_key": "proposal",
            "probability_action_changes_outcome": 0.8,
            "incremental_revenue_if_changed_cents": 20000,
            "action_cost_cents": 3000,
            "confidence": 1.0,
            "capacity_group": "proposal",
            "evidence_refs": ["nba:proposal"],
        },
    ]
    plan = optimize_action_portfolio(
        nba_actions=raw,
        budget_cents=5000,
        capacity_constraints={"outreach": 1, "proposal": 1},
    )
    assert plan["status"] == "AVAILABLE"
    assert plan["nba_context"]["total_nba_actions"] == 2
    assert plan["nba_context"]["unavailable_nba_actions"] == 0
    assert plan["nba_context"]["nba_recommendation_only"] is True
    assert plan["actual_revenue"] is False
    assert plan["execution_authority"] == "none"


def test_benchmark_review_requires_complete_evidence():
    review = review_portfolio_benchmark(
        plan=build_portfolio_optimization_plan(_problem()),
        candidate={"objective_value_cents": 20000},
    )
    assert review["status"] == "UNAVAILABLE"
    assert "constraints_satisfied" in review["missing_fields"]


def test_benchmark_review_never_auto_promotes():
    plan = build_portfolio_optimization_plan(_problem())
    reference = plan["classical_exact"]["objective_value_cents"]
    review = review_portfolio_benchmark(
        plan=plan,
        candidate={
            "solver": "qaoa_simulator",
            "objective_value_cents": reference + 1,
            "constraints_satisfied": True,
            "wall_clock_ms": 25,
            "compute_cost_minor_units": 0,
        },
    )
    assert review["status"] == "AVAILABLE"
    assert review["matches_or_beats_reference"] is True
    assert review["production_promotion_ready"] is False
    assert review["quantum_advantage_claimed"] is False
    assert review["human_review_required"] is True
    assert review["execution_authority"] == "none"
