import pytest

from empire_os.intelligence_optimization_fabric import (
    build_allocation_fabric_plan,
    build_optimization_fabric_plan,
)
from empire_os.optimization_benchmark_arena import run_benchmark_arena
from empire_os.predictive_cloud_scenario_optimization import (
    build_predictive_cloud_scenario_problem,
)
from empire_os.quantum_optimization import (
    build_allocation_optimization_problem,
)
from empire_os.solver_intelligence import discover_solver_runtime


def _allocation_plan():
    source = build_allocation_optimization_problem(
        options=[
            {
                "prospect_id": "p1",
                "buyer_id": "b1",
                "expected_value_cents": 1000,
                "evidence_refs": ["ev:p1-b1"],
            },
            {
                "prospect_id": "p1",
                "buyer_id": "b2",
                "expected_value_cents": 100,
                "evidence_refs": ["ev:p1-b2"],
            },
        ],
        buyer_capacities={"b1": 1, "b2": 1},
    )
    return build_allocation_fabric_plan(
        source,
        runtime=discover_solver_runtime(),
        time_budget_ms=1000,
    )


def test_arena_runs_empire_owned_solvers_on_same_problem():
    plan = _allocation_plan()

    result = run_benchmark_arena(
        plan,
        annealing_num_reads=50,
        annealing_num_sweeps=500,
        annealing_seed=1729,
        observed_at="2026-10-02T22:30:00+00:00",
    )

    assert result["status"] == "AVAILABLE"
    assert result["run_count"] == 6
    assert result["baseline_solver"] == "classical_exact_binary_ir"
    assert result["solver_origin"] == "empire_owned"
    assert result["third_party_runtime_dependency"] is False
    assert result["runs"]["classical_exact_binary_ir"][
        "problem_fingerprint"
    ] == result["problem_fingerprint"]
    assert result["runs"]["empire_branch_bound"][
        "problem_fingerprint"
    ] == result["problem_fingerprint"]
    assert result["runs"]["empire_annealing"][
        "problem_fingerprint"
    ] == result["problem_fingerprint"]
    assert result["runs"]["empire_parallel_tempering"][
        "problem_fingerprint"
    ] == result["problem_fingerprint"]
    assert result["runs"]["empire_qaoa_simulator"][
        "problem_fingerprint"
    ] == result["problem_fingerprint"]
    assert result["comparisons"]["empire_branch_bound"][
        "matches_or_beats_reference"
    ] is True
    assert result["comparisons"]["empire_annealing"][
        "matches_or_beats_reference"
    ] is True
    assert result["external_qpu_called"] is False
    assert result["quantum_advantage_claimed"] is False
    assert result["automatic_production_routing_changed"] is False


def test_arena_keeps_general_budget_problem_out_of_qubo_lane():
    problem = build_predictive_cloud_scenario_problem(
        scenarios=[
            {
                "scenario_key": "base",
                "probability": 1.0,
                "evidence_refs": ["scenario:base"],
            }
        ],
        actions=[
            {
                "action_key": "a1",
                "scenario_values_cents": {"base": 1000},
                "action_cost_cents": 500,
                "evidence_refs": ["action:a1"],
            },
            {
                "action_key": "a2",
                "scenario_values_cents": {"base": 900},
                "action_cost_cents": 500,
                "evidence_refs": ["action:a2"],
            },
        ],
        budget_cents=500,
        time_budget_ms=1000,
    )
    plan = build_optimization_fabric_plan(
        problem,
        runtime=discover_solver_runtime(),
    )

    result = run_benchmark_arena(
        plan,
        observed_at="2026-10-02T22:31:00+00:00",
    )

    assert result["status"] == "AVAILABLE"
    assert "empire_annealing" not in result["runs"]
    assert result["unavailable_lanes"]["safe_qubo"]["reason"] in {
        "general_constraint_requires_cqm_or_slack_encoding",
        "non_unit_constraint_coefficient_requires_cqm",
    }
    assert result["external_qpu_called"] is False
    assert result["quantum_advantage_claimed"] is False

def test_market_references_are_explicit_and_do_not_feed_policy():
    pytest.importorskip("ortools")
    plan = _allocation_plan()

    result = run_benchmark_arena(
        plan,
        include_market_references=True,
        observed_at="2026-10-02T22:32:00+00:00",
    )

    assert result["market_references_included"] is True
    assert result["market_reference_run_count"] >= 1
    assert "ortools_cp_sat" in result["market_reference_runs"]
    assert "ortools_cp_sat" not in result["runs"]
    assert result["market_reference_feeds_solver_policy"] is False
