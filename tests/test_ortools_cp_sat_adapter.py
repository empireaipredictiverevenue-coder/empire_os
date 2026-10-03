import pytest

pytest.importorskip("ortools")

from empire_os.intelligence_optimization_fabric import (
    build_optimization_fabric_plan,
)
from empire_os.predictive_cloud_scenario_optimization import (
    build_predictive_cloud_scenario_problem,
)
from empire_os.solver_adapters.ortools_cp_sat import solve_cp_sat
from empire_os.solver_intelligence import discover_solver_runtime


def _problem(*, time_budget_ms=2000, risk_aversion=0.8):
    return build_predictive_cloud_scenario_problem(
        scenarios=[
            {
                "scenario_key": "base",
                "probability": 0.6,
                "evidence_refs": ["scenario:base"],
            },
            {
                "scenario_key": "downside",
                "probability": 0.4,
                "evidence_refs": ["scenario:downside"],
            },
        ],
        actions=[
            {
                "action_key": "high_upside",
                "scenario_values_cents": {
                    "base": 10000,
                    "downside": 2000,
                },
                "action_cost_cents": 1000,
                "evidence_refs": ["action:high_upside"],
            },
            {
                "action_key": "resilient",
                "scenario_values_cents": {
                    "base": 7000,
                    "downside": 6000,
                },
                "action_cost_cents": 1000,
                "evidence_refs": ["action:resilient"],
            },
        ],
        budget_cents=1000,
        risk_aversion=risk_aversion,
        time_budget_ms=time_budget_ms,
    )


def test_cp_sat_solves_risk_aware_predictive_cloud_problem():
    problem = _problem()

    result = solve_cp_sat(problem, max_workers=1)

    assert result["status"] == "AVAILABLE"
    assert result["solve_status"] == "OPTIMAL"
    assert result["selected_variables"] == ["x::resilient"]
    assert result["objective_value"] == 6120.0
    assert result["constraints_satisfied"] is True
    assert result["compute_cost_minor_units"] is None
    assert result["compute_cost_known"] is False
    assert result["execution_authority"] == "none"


def test_cp_sat_requires_bounded_time_budget():
    problem = _problem(time_budget_ms=None)

    result = solve_cp_sat(problem)

    assert result["status"] == "UNAVAILABLE"
    assert result["reason"] == "time_budget_required"


def test_router_discovers_installed_cp_sat_and_routes_bounded_generic_workload():
    problem = _problem(time_budget_ms=1500)
    runtime = discover_solver_runtime()

    plan = build_optimization_fabric_plan(
        problem,
        runtime=runtime,
        exact_variable_limit=1,
    )

    assert runtime["packages"]["ortools"] is True
    assert runtime["market_reference_adapters"]["ortools_cp_sat"] is True
    assert plan["primary_solver"] == "empire_branch_bound"
    lane = next(
        row for row in plan["solver_route"]["benchmark_lanes"]
        if row["solver"] == "ortools_cp_sat"
    )
    assert lane["runnable"] is False
    assert lane["purpose"] == "market_reference_only"
    assert "third_party_runtime_not_allowed" in lane["blockers"]
    assert plan["solver_execution_ready"] is True
    assert plan["production_promotion_ready"] is False


def test_router_does_not_route_cp_sat_without_time_budget():
    problem = _problem(time_budget_ms=None)
    runtime = discover_solver_runtime()

    plan = build_optimization_fabric_plan(
        problem,
        runtime=runtime,
        exact_variable_limit=1,
    )

    cp_sat = next(
        row for row in plan["solver_route"]["benchmark_lanes"]
        if row["solver"] == "ortools_cp_sat"
    )
    assert cp_sat["runnable"] is False
    assert "time_budget_required" in cp_sat["blockers"]
    assert plan["primary_solver"] == "classical_greedy_reference"
    assert plan["solver_execution_ready"] is True
