from empire_os.intelligence_optimization_fabric import (
    build_allocation_fabric_plan,
)
from empire_os.optimization_qubo import build_safe_qubo
from empire_os.quantum_optimization import (
    build_allocation_optimization_problem,
)
from empire_os.solver_adapters.empire_tabu import solve_empire_tabu


def _qubo():
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
            {
                "prospect_id": "p2",
                "buyer_id": "b1",
                "expected_value_cents": 200,
                "evidence_refs": ["ev:p2-b1"],
            },
            {
                "prospect_id": "p2",
                "buyer_id": "b2",
                "expected_value_cents": 900,
                "evidence_refs": ["ev:p2-b2"],
            },
        ],
        buyer_capacities={"b1": 1, "b2": 1},
    )
    plan = build_allocation_fabric_plan(source, time_budget_ms=1500)
    return build_safe_qubo(plan["problem"])


def test_empire_tabu_finds_reference_optimum_on_fixture():
    result = solve_empire_tabu(
        _qubo(),
        iterations=400,
        tabu_tenure=7,
        restart_interval=80,
        seed=1729,
    )

    assert result["status"] == "AVAILABLE"
    assert result["objective_value"] == 1900.0
    assert result["selected_variables"] == [
        "x::p1::b1",
        "x::p2::b2",
    ]
    assert result["constraints_satisfied"] is True
    assert result["qpu_called"] is False
    assert result["third_party_runtime_dependency"] is False


def test_empire_tabu_is_reproducible_with_fixed_seed():
    left = solve_empire_tabu(
        _qubo(), iterations=120, restart_interval=40, seed=42
    )
    right = solve_empire_tabu(
        _qubo(), iterations=120, restart_interval=40, seed=42
    )

    assert left["selected_variables"] == right["selected_variables"]
    assert left["objective_value"] == right["objective_value"]
    assert left["qubo_energy"] == right["qubo_energy"]
