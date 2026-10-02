from empire_os.intelligence_optimization_fabric import (
    build_action_portfolio_fabric_plan,
    build_allocation_fabric_plan,
    build_optimization_fabric_plan,
)
from empire_os.action_portfolio_optimization import (
    build_portfolio_optimization_problem,
)
from empire_os.optimization_problem_factory import build_problem_ir
from empire_os.quantum_optimization import build_allocation_optimization_problem


def _empty_runtime():
    return {
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


def test_allocation_fabric_preserves_existing_exact_reference():
    source = build_allocation_optimization_problem(
        options=[
            {
                "prospect_id": "p1",
                "buyer_id": "b1",
                "expected_value_cents": 1000,
                "evidence_refs": ["ev:1"],
            }
        ],
        buyer_capacities={"b1": 1},
    )

    plan = build_allocation_fabric_plan(
        source,
        tenant_id="tenant-a",
        runtime=_empty_runtime(),
    )

    assert plan["status"] == "AVAILABLE"
    assert plan["tenant_id"] == "tenant-a"
    assert plan["primary_solver"] == "classical_exact_reference"
    assert plan["solver_execution_ready"] is True
    assert plan["qaoa_model_eligible"] is True
    assert plan["production_promotion_ready"] is False
    assert plan["execution_authority"] == "none"


def test_action_portfolio_fabric_does_not_advertise_unvalidated_qubo():
    source = build_portfolio_optimization_problem(
        actions=[
            {
                "action_key": "a1",
                "expected_incremental_value_cents": 5000,
                "action_cost_cents": 500,
                "evidence_refs": ["ev:a1"],
            }
        ],
        budget_cents=1000,
    )

    plan = build_action_portfolio_fabric_plan(
        source,
        runtime=_empty_runtime(),
    )

    assert plan["qaoa_model_eligible"] is False
    assert plan["cqm_model_eligible"] is True
    assert plan["primary_solver"] == "classical_exact_reference"


def test_large_unknown_workload_has_no_fake_builtin_solver():
    variables = [
        {"variable": f"x::{index}", "evidence_refs": [f"ev:{index}"]}
        for index in range(25)
    ]
    problem = build_problem_ir(
        workload_key="new_workload",
        workload_type="new_future_workload",
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
        representations=("CQM",),
    )

    plan = build_optimization_fabric_plan(
        problem,
        runtime=_empty_runtime(),
    )

    assert plan["status"] == "AVAILABLE"
    assert plan["primary_solver"] is None
    assert plan["solver_execution_ready"] is False
    assert plan["solver_route"]["routing_reason"] == (
        "no_implemented_solver_for_workload"
    )
    assert plan["execution_authority"] == "none"
