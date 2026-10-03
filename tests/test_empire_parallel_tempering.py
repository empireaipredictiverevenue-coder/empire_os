from empire_os.intelligence_optimization_fabric import (
    build_allocation_fabric_plan,
)
from empire_os.optimization_qubo import build_safe_qubo
from empire_os.quantum_optimization import (
    build_allocation_optimization_problem,
)
from empire_os.solver_adapters.empire_parallel_tempering import (
    solve_empire_parallel_tempering,
)


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


def test_parallel_tempering_recovers_optimum_without_external_runtime():
    result = solve_empire_parallel_tempering(
        _qubo(),
        replica_count=8,
        rounds=120,
        sweeps_per_round=3,
        seed=314159,
        max_wall_clock_ms=1500,
    )

    assert result["status"] == "AVAILABLE"
    assert result["objective_value"] == 1900.0
    assert result["selected_variables"] == [
        "x::p1::b1",
        "x::p2::b2",
    ]
    assert result["constraints_satisfied"] is True
    assert result["replica_exchange"] is True
    assert result["swap_attempts"] > 0
    assert result["qpu_called"] is False
    assert result["third_party_runtime_dependency"] is False
    assert result["quantum_advantage_claimed"] is False


def test_parallel_tempering_is_reproducible_with_fixed_seed():
    qubo = _qubo()
    left = solve_empire_parallel_tempering(
        qubo,
        replica_count=6,
        rounds=40,
        sweeps_per_round=2,
        seed=99,
    )
    right = solve_empire_parallel_tempering(
        qubo,
        replica_count=6,
        rounds=40,
        sweeps_per_round=2,
        seed=99,
    )

    assert left["selected_variables"] == right["selected_variables"]
    assert left["objective_value"] == right["objective_value"]
    assert left["qubo_energy"] == right["qubo_energy"]
    assert left["accepted_swaps"] == right["accepted_swaps"]


def test_parallel_tempering_fails_closed_on_unvalidated_qubo():
    result = solve_empire_parallel_tempering({
        "status": "AVAILABLE",
        "local_bqm_ready": False,
    })

    assert result["status"] == "UNAVAILABLE"
    assert result["reason"] == (
        "qubo_not_validated_for_empire_parallel_tempering"
    )
