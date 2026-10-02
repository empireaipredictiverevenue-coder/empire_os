from empire_os.agi_orchestrator import build_agi_orchestration_packet
from empire_os.intelligence_optimization_fabric import (
    build_optimization_fabric_plan,
)
from empire_os.predictive_cloud_scenario_optimization import (
    build_predictive_cloud_scenario_problem,
)


def test_agi_detects_missing_solver_lane_for_v2_optimization_fabric():
    problem = build_predictive_cloud_scenario_problem(
        scenarios=[
            {
                "scenario_key": "base",
                "probability": 0.7,
                "evidence_refs": ["scenario:base"],
            },
            {
                "scenario_key": "downside",
                "probability": 0.3,
                "evidence_refs": ["scenario:downside"],
            },
        ],
        actions=[
            {
                "action_key": "expand",
                "scenario_values_cents": {
                    "base": 10000,
                    "downside": 3000,
                },
                "action_cost_cents": 1000,
                "evidence_refs": ["action:expand"],
            },
            {
                "action_key": "retain",
                "scenario_values_cents": {
                    "base": 7000,
                    "downside": 6500,
                },
                "action_cost_cents": 500,
                "evidence_refs": ["action:retain"],
            }
        ],
        budget_cents=1000,
    )
    empty_runtime = {
        "packages": {
            "ortools": False,
            "pyomo": False,
            "dimod": False,
            "dwave_system": False,
            "qiskit": False,
            "pennylane": False,
            "amazon_braket": False,
            "cirq": False,
        },
        "provider_flags": {
            "ibm_quantum": False,
            "dwave": False,
            "amazon_braket": False,
        },
        "empire_adapters": {
            "ortools_cp_sat": False,
            "pyomo_mip": False,
            "local_bqm_quantum_inspired": False,
            "dwave_hybrid_cqm": False,
            "ibm_qaoa": False,
            "amazon_braket_qaoa": False,
            "pennylane_qaoa": False,
        },
    }
    fabric = build_optimization_fabric_plan(
        problem,
        runtime=empty_runtime,
        exact_variable_limit=1,
    )

    packet = build_agi_orchestration_packet(
        task_id="agi-opt-v2",
        goal="Choose an evidence-backed action portfolio",
        world_state_ref="world:1",
        evidence_refs=["world:1"],
        predictive_revenue={
            "status": "AVAILABLE",
            "expected_revenue_value_cents": 10000,
            "actual_revenue": False,
        },
        predictive_cloud={
            "status": "AVAILABLE",
            "cloud_operating_score": 80,
            "constraints": {"state": "CLEAR"},
            "actual_revenue": False,
        },
        future_trend={
            "status": "AVAILABLE",
            "future_opportunity_status": "AVAILABLE",
            "trend_confidence": 0.8,
            "trend_opportunity_alignment": 0.7,
            "causal_claim": False,
        },
        quantum_optimization=fabric,
        economic_memory={
            "status": "AVAILABLE",
            "verified_outcomes_only_for_outcome_conditioned_memory": True,
            "model_weight_mutation_authorized": False,
        },
    )

    review = packet["specialist_reviews"]["quantum_optimization"]
    assert review["optimization_fabric_v2"] is True
    assert review["solver_execution_ready"] is False
    assert review["solver_routing_reason"] == (
        "no_implemented_solver_for_workload"
    )
    assert packet["recommended_cognitive_workstream"]["workstream"] == (
        "establish_compatible_solver_lane"
    )
    assert packet["execution_ready"] is False
    assert packet["execution_authority"] == "none"
