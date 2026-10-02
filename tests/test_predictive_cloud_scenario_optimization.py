from empire_os.intelligence_optimization_fabric import (
    build_optimization_fabric_plan,
)
from empire_os.predictive_cloud_scenario_optimization import (
    build_predictive_cloud_scenario_problem,
)


SCENARIOS = [
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
]


def _actions():
    return [
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
    ]


def _objective(problem):
    return dict(problem["objective"]["linear"])


def test_scenario_probabilities_must_be_explicit_and_sum_to_one():
    packet = build_predictive_cloud_scenario_problem(
        scenarios=[
            {
                "scenario_key": "base",
                "probability": 0.8,
                "evidence_refs": ["scenario:base"],
            },
            {
                "scenario_key": "downside",
                "probability": 0.3,
                "evidence_refs": ["scenario:downside"],
            },
        ],
        actions=_actions(),
        budget_cents=2000,
    )

    assert packet["status"] == "UNAVAILABLE"
    assert packet["reason"] == "scenario_probabilities_must_sum_to_one"
    assert packet["probability_normalized_implicitly"] is False
    assert packet["unknown_is_zero"] is False


def test_missing_action_scenario_value_is_blocked_not_zero_filled():
    actions = _actions()
    del actions[0]["scenario_values_cents"]["downside"]

    packet = build_predictive_cloud_scenario_problem(
        scenarios=SCENARIOS,
        actions=actions,
        budget_cents=2000,
    )

    blocked = packet["metadata"]["blocked_actions"]
    assert any(
        row.get("action_key") == "high_upside"
        and "scenario_values_cents:downside" in row.get("missing_fields", [])
        for row in blocked
    )
    assert all(
        row["action_key"] != "high_upside"
        for row in packet["variables"]
    )


def test_explicit_risk_policy_changes_relative_action_value():
    growth = build_predictive_cloud_scenario_problem(
        scenarios=SCENARIOS,
        actions=_actions(),
        budget_cents=2000,
        risk_aversion=0.0,
    )
    defensive = build_predictive_cloud_scenario_problem(
        scenarios=SCENARIOS,
        actions=_actions(),
        budget_cents=2000,
        risk_aversion=0.8,
    )

    growth_values = _objective(growth)
    defensive_values = _objective(defensive)

    assert growth_values["x::high_upside"] > growth_values["x::resilient"]
    assert defensive_values["x::resilient"] > defensive_values["x::high_upside"]
    assert defensive["metadata"]["risk_aversion"] == 0.8
    assert defensive["actual_revenue"] is False
    assert defensive["execution_authority"] == "none"


def test_predictive_cloud_problem_enters_common_fabric_with_exact_small_reference():
    problem = build_predictive_cloud_scenario_problem(
        scenarios=SCENARIOS,
        actions=_actions(),
        budget_cents=2000,
        risk_aversion=0.25,
        tenant_id="tenant-a",
    )
    plan = build_optimization_fabric_plan(problem)

    assert problem["status"] == "AVAILABLE"
    assert problem["workload_type"] == "predictive_cloud_scenario_portfolio"
    assert problem["representations"] == ["CQM"]
    assert plan["status"] == "AVAILABLE"
    assert plan["solver_execution_ready"] is True
    assert plan["primary_solver"] == "classical_exact_reference"
    assert plan["primary_reference_quality"] == "OPTIMAL_REFERENCE"
    assert plan["production_promotion_ready"] is False
