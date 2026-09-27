from empire_os.hybrid_optimization import (
    build_hybrid_optimization_plan,
    review_hybrid_benchmark,
    solve_allocation_classical_greedy,
)
from empire_os.quantum_optimization import (
    build_allocation_optimization_problem,
)


def _problem(capacities=None):
    options = [
        {
            "prospect_id": "p1",
            "buyer_id": "b1",
            "expected_value_cents": 10000,
            "evidence_refs": ["erv:p1:b1"],
        },
        {
            "prospect_id": "p1",
            "buyer_id": "b2",
            "expected_value_cents": 9000,
            "evidence_refs": ["erv:p1:b2"],
        },
        {
            "prospect_id": "p2",
            "buyer_id": "b1",
            "expected_value_cents": 8000,
            "evidence_refs": ["erv:p2:b1"],
        },
        {
            "prospect_id": "p2",
            "buyer_id": "b2",
            "expected_value_cents": 7000,
            "evidence_refs": ["erv:p2:b2"],
        },
    ]
    return build_allocation_optimization_problem(
        options=options,
        buyer_capacities=capacities or {"b1": 1, "b2": 1},
    )


def test_greedy_baseline_respects_capacity_and_one_per_prospect():
    result = solve_allocation_classical_greedy(_problem())
    assert result["status"] == "AVAILABLE"
    assert result["selected_count"] == 2
    assert result["objective_value_cents"] == 17000
    assert result["optimal_for_normalized_problem"] is False
    assert result["allocation_execution"] is False


def test_hybrid_plan_uses_exact_reference_for_small_problem():
    plan = build_hybrid_optimization_plan(_problem())
    assert plan["status"] == "AVAILABLE"
    assert plan["primary_classical_lane"] == "classical_exact"
    assert plan["classical_reference_quality"] == "OPTIMAL_REFERENCE"
    assert plan["quantum_benchmark_lane"] == "QAOA_OR_BQM_BENCHMARK"
    assert plan["benchmark_ready"] is True
    assert plan["production_promotion_ready"] is False
    assert plan["quantum_advantage_claimed"] is False


def test_hybrid_plan_uses_cqm_for_general_capacity():
    plan = build_hybrid_optimization_plan(
        _problem({"b1": 2, "b2": 1})
    )
    assert plan["status"] == "AVAILABLE"
    assert plan["unit_capacity_problem"] is False
    assert plan["quantum_benchmark_lane"] == "CQM_HYBRID_BENCHMARK"
    assert plan["qubo_export"]["status"] == "UNAVAILABLE"
    assert plan["cqm_export"]["status"] == "AVAILABLE"


def test_large_problem_falls_back_to_greedy_reference():
    problem = _problem()
    plan = build_hybrid_optimization_plan(
        problem,
        exact_variable_limit=2,
    )
    assert plan["primary_classical_lane"] == "classical_greedy"
    assert plan["classical_reference_quality"] == "HEURISTIC_REFERENCE"
    assert plan["classical_exact"]["status"] == "UNAVAILABLE"
    assert plan["benchmark_ready"] is True


def test_benchmark_review_requires_complete_evidence():
    plan = build_hybrid_optimization_plan(_problem())
    review = review_hybrid_benchmark(
        plan=plan,
        candidate={
            "solver": "qaoa_simulator",
            "objective_value_cents": 17000,
        },
    )
    assert review["status"] == "UNAVAILABLE"
    assert "constraints_satisfied" in review["missing_fields"]


def test_benchmark_review_never_auto_promotes():
    plan = build_hybrid_optimization_plan(_problem())
    review = review_hybrid_benchmark(
        plan=plan,
        candidate={
            "solver": "qaoa_simulator",
            "objective_value_cents": 17000,
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
