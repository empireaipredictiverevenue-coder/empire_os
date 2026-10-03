from empire_os.intelligence_optimization_fabric import (
    build_allocation_fabric_plan,
)
from empire_os.optimization_qubo import build_safe_qubo
from empire_os.quantum_optimization import (
    build_allocation_optimization_problem,
)
from empire_os.solver_adapters.empire_annealing import (
    solve_empire_annealing,
)
from empire_os.solver_adapters.exact_binary import solve_exact_binary


def _plan():
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
    return build_allocation_fabric_plan(
        source,
        time_budget_ms=1500,
    )


def test_empire_annealing_matches_exact_on_safe_qubo_fixture():
    plan = _plan()
    qubo = build_safe_qubo(plan["problem"])
    exact = solve_exact_binary(plan["problem"])
    result = solve_empire_annealing(
        qubo,
        num_reads=96,
        sweeps_per_read=600,
        seed=1729,
        max_wall_clock_ms=1500,
    )

    assert qubo["status"] == "AVAILABLE"
    assert exact["objective_value"] == 1900.0
    assert result["status"] == "AVAILABLE"
    assert result["objective_value"] == 1900.0
    assert result["selected_variables"] == [
        "x::p1::b1",
        "x::p2::b2",
    ]
    assert result["constraints_satisfied"] is True
    assert result["qpu_called"] is False
    assert result["third_party_runtime_dependency"] is False
    assert result["quantum_advantage_claimed"] is False


def test_empire_annealing_is_reproducible_with_fixed_seed():
    qubo = build_safe_qubo(_plan()["problem"])
    left = solve_empire_annealing(
        qubo,
        num_reads=24,
        sweeps_per_read=200,
        seed=42,
    )
    right = solve_empire_annealing(
        qubo,
        num_reads=24,
        sweeps_per_read=200,
        seed=42,
    )

    assert left["selected_variables"] == right["selected_variables"]
    assert left["objective_value"] == right["objective_value"]
    assert left["qubo_energy"] == right["qubo_energy"]


def test_empire_annealing_fails_closed_on_unvalidated_qubo():
    result = solve_empire_annealing({
        "status": "AVAILABLE",
        "local_bqm_ready": False,
    })

    assert result["status"] == "UNAVAILABLE"
    assert result["reason"] == "qubo_not_validated_for_empire_annealing"
