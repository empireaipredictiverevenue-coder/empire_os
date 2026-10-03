import pytest

pytest.importorskip("dimod")
pytest.importorskip("dwave.samplers")

from empire_os.intelligence_optimization_fabric import (
    build_allocation_fabric_plan,
)
from empire_os.optimization_qubo import build_safe_qubo
from empire_os.optimization_runtime import (
    compare_local_qubo_with_exact_reference,
)
from empire_os.quantum_optimization import (
    build_allocation_optimization_problem,
)
from empire_os.solver_adapters.dwave_local import (
    solve_simulated_annealing,
)
from empire_os.solver_intelligence import discover_solver_runtime


def _source():
    return build_allocation_optimization_problem(
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


def test_local_simulated_annealing_solves_safe_qubo_without_qpu():
    plan = build_allocation_fabric_plan(
        _source(),
        runtime=discover_solver_runtime(),
    )
    qubo = build_safe_qubo(plan["problem"])
    result = solve_simulated_annealing(
        qubo,
        num_reads=50,
        num_sweeps=1000,
        seed=1729,
    )

    assert result["status"] == "AVAILABLE"
    assert result["selected_variables"] == ["x::p1::b1"]
    assert result["objective_value"] == 1000.0
    assert result["constraints_satisfied"] is True
    assert result["qpu_called"] is False
    assert result["quantum_advantage_claimed"] is False


def test_runtime_discovers_local_quantum_inspired_lane():
    runtime = discover_solver_runtime()
    plan = build_allocation_fabric_plan(
        _source(),
        runtime=runtime,
    )
    lane = next(
        row
        for row in plan["solver_route"]["benchmark_lanes"]
        if row["solver"] == "local_bqm_quantum_inspired"
    )

    assert runtime["packages"]["dimod"] is True
    assert runtime["packages"]["dwave_samplers"] is True
    assert lane["runnable"] is True
    assert lane["purpose"] == "benchmark_only"


def test_local_quantum_inspired_candidate_is_bound_to_exact_reference():
    plan = build_allocation_fabric_plan(
        _source(),
        runtime=discover_solver_runtime(),
    )

    review = compare_local_qubo_with_exact_reference(
        plan,
        num_reads=50,
        num_sweeps=1000,
        seed=1729,
        observed_at="2026-10-02T22:00:00+00:00",
    )

    assert review["status"] == "AVAILABLE"
    assert review["same_problem_verified"] is True
    assert review["exact"]["objective_value"] == 1000.0
    assert review["candidate"]["objective_value"] == 1000.0
    assert review["candidate"]["qpu_called"] is False
    assert review["comparison"]["matches_or_beats_reference"] is True
    assert review["quantum_advantage_claimed"] is False
