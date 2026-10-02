import pytest

pytest.importorskip("ortools")

from empire_os.intelligence_optimization_fabric import (
    build_optimization_fabric_plan,
)
from empire_os.optimization_runtime import (
    compare_cp_sat_with_exact_reference,
    execute_primary_solver,
)
from empire_os.predictive_cloud_scenario_optimization import (
    build_predictive_cloud_scenario_problem,
)
from empire_os.solver_intelligence import discover_solver_runtime


def _scenario_problem():
    return build_predictive_cloud_scenario_problem(
        scenarios=[
            {
                "scenario_key": "base",
                "probability": 0.6,
                "evidence_refs": ["s:base"],
            },
            {
                "scenario_key": "downside",
                "probability": 0.4,
                "evidence_refs": ["s:downside"],
            },
        ],
        actions=[
            {
                "action_key": "high",
                "scenario_values_cents": {
                    "base": 10000,
                    "downside": 2000,
                },
                "action_cost_cents": 1000,
                "evidence_refs": ["a:high"],
            },
            {
                "action_key": "resilient",
                "scenario_values_cents": {
                    "base": 7000,
                    "downside": 6000,
                },
                "action_cost_cents": 1000,
                "evidence_refs": ["a:resilient"],
            },
        ],
        budget_cents=1000,
        risk_aversion=0.8,
        time_budget_ms=2000,
    )


def test_runtime_executes_generic_exact_primary_for_small_problem():
    problem = _scenario_problem()
    plan = build_optimization_fabric_plan(
        problem,
        runtime=discover_solver_runtime(),
    )

    assert plan["primary_solver"] == "classical_exact_reference"

    result = execute_primary_solver(plan)

    assert result["status"] == "AVAILABLE"
    assert result["result"]["selected_variables"] == ["x::resilient"]
    assert result["result"]["objective_value"] == 6120.0
    assert result["external_action_performed"] is False
    assert result["execution_authority"] == "none"


def test_runtime_benchmarks_cp_sat_against_same_exact_problem():
    problem = _scenario_problem()
    plan = build_optimization_fabric_plan(
        problem,
        runtime=discover_solver_runtime(),
    )

    review = compare_cp_sat_with_exact_reference(
        plan,
        observed_at="2026-10-02T21:30:00+00:00",
    )

    assert review["status"] == "AVAILABLE"
    assert review["same_problem_verified"] is True
    assert review["exact"]["objective_value"] == 6120.0
    assert review["cp_sat"]["objective_value"] == 6120.0
    assert review["comparison"]["matches_or_beats_reference"] is True
    assert review["comparison"]["compute_cost_comparable"] is False
    assert review["quantum_advantage_claimed"] is False


def test_generic_exact_reference_fails_closed_above_universal_limit():
    from empire_os.optimization_problem_factory import build_problem_ir
    from empire_os.solver_adapters.exact_binary import (
        DEFAULT_MAX_VARIABLES,
        solve_exact_binary,
    )

    count = DEFAULT_MAX_VARIABLES + 1
    variables = [
        {
            "variable": f"x::{index}",
            "evidence_refs": [f"evidence:{index}"],
        }
        for index in range(count)
    ]
    problem = build_problem_ir(
        workload_key="exact-limit",
        workload_type="generic_binary_portfolio",
        source_schema_version="fixture.v1",
        variable_type="BINARY",
        variables=variables,
        objective={
            "sense": "MAXIMIZE",
            "linear": {
                row["variable"]: 1
                for row in variables
            },
            "quadratic": {},
        },
        constraints=[],
    )

    result = solve_exact_binary(problem)

    assert result["status"] == "UNAVAILABLE"
    assert result["reason"] == "exact_reference_variable_limit_exceeded"
    assert result["max_variables"] == DEFAULT_MAX_VARIABLES


def test_runtime_parallelizes_proven_independent_large_cp_sat_problem():
    from empire_os.optimization_problem_factory import build_problem_ir

    variables = [
        {
            "variable": f"x::{index}",
            "partition_key": "north" if index < 10 else "south",
            "evidence_refs": [f"evidence:{index}"],
        }
        for index in range(20)
    ]
    problem = build_problem_ir(
        workload_key="parallel-runtime",
        workload_type="generic_binary_portfolio",
        source_schema_version="fixture.v1",
        variable_type="BINARY",
        variables=variables,
        objective={
            "sense": "MAXIMIZE",
            "linear": {
                row["variable"]: index + 1
                for index, row in enumerate(variables)
            },
            "quadratic": {},
        },
        constraints=[
            {
                "name": "north_capacity",
                "coefficients": {
                    f"x::{index}": 1
                    for index in range(10)
                },
                "sense": "<=",
                "rhs": 1,
            },
            {
                "name": "south_capacity",
                "coefficients": {
                    f"x::{index}": 1
                    for index in range(10, 20)
                },
                "sense": "<=",
                "rhs": 1,
            },
        ],
        time_budget_ms=2000,
        representations=("CQM",),
    )
    plan = build_optimization_fabric_plan(
        problem,
        runtime=discover_solver_runtime(),
        max_variables_per_shard=10,
    )

    assert plan["primary_solver"] == "ortools_cp_sat"
    assert plan["decomposition"]["strategy"] == "independent_shards"

    executed = execute_primary_solver(plan, max_workers=2)
    result = executed["result"]

    assert executed["status"] == "AVAILABLE"
    assert result["strategy"] == "independent_shards"
    assert result["shard_count"] == 2
    assert result["selected_variables"] == ["x::19", "x::9"]
    assert result["objective_value"] == 30.0
    assert result["constraints_satisfied"] is True
    assert result["execution_authority"] == "none"
