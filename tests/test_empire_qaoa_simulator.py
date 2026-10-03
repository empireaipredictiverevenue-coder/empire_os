from empire_os.intelligence_optimization_fabric import (
    build_allocation_fabric_plan,
)
from empire_os.optimization_qubo import build_safe_qubo
from empire_os.quantum_optimization import (
    build_allocation_optimization_problem,
)
from empire_os.solver_adapters.empire_qaoa_simulator import (
    solve_empire_qaoa_simulator,
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


def test_qaoa_simulator_recovers_optimum_without_qpu():
    result = solve_empire_qaoa_simulator(
        _qubo(),
        gamma_steps=17,
        beta_steps=13,
        max_wall_clock_ms=1500,
    )

    assert result["status"] == "AVAILABLE"
    assert result["objective_value"] == 1900.0
    assert result["selected_variables"] == [
        "x::p1::b1",
        "x::p2::b2",
    ]
    assert result["constraints_satisfied"] is True
    assert result["qaoa_depth"] == 1
    assert result["statevector_dimension"] == 16
    assert result["statevector_norm"] == 1.0
    assert result["angle_evaluations"] == 221
    assert result["quantum_simulator"] is True
    assert result["real_qpu"] is False
    assert result["qpu_called"] is False
    assert result["third_party_runtime_dependency"] is False
    assert result["benchmark_only"] is True
    assert result["quantum_advantage_claimed"] is False


def test_qaoa_simulator_is_deterministic_for_same_grid():
    left = solve_empire_qaoa_simulator(
        _qubo(),
        gamma_steps=9,
        beta_steps=7,
    )
    right = solve_empire_qaoa_simulator(
        _qubo(),
        gamma_steps=9,
        beta_steps=7,
    )

    assert left["selected_variables"] == right["selected_variables"]
    assert left["objective_value"] == right["objective_value"]
    assert left["expected_qubo_energy"] == right["expected_qubo_energy"]
    assert left["best_gamma"] == right["best_gamma"]
    assert left["best_beta"] == right["best_beta"]


def test_qaoa_simulator_enforces_statevector_variable_limit():
    qubo = _qubo()
    result = solve_empire_qaoa_simulator(
        qubo,
        max_qubits=3,
    )

    assert result["status"] == "UNAVAILABLE"
    assert result["reason"] == "statevector_qubit_limit_exceeded"


def test_qaoa_simulator_fails_closed_when_qaoa_not_validated():
    result = solve_empire_qaoa_simulator({
        "status": "AVAILABLE",
        "qaoa_ready": False,
    })

    assert result["status"] == "UNAVAILABLE"
    assert result["reason"] == "qubo_not_validated_for_qaoa"
