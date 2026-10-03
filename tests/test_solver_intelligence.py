from empire_os.optimization_problem_factory import build_problem_ir
from empire_os.solver_intelligence import route_solver


def _problem(count=2, *, cost_budget_minor_units=None, time_budget_ms=None):
    variables = [
        {
            "variable": f"x::{index}",
            "evidence_refs": [f"evidence:{index}"],
        }
        for index in range(count)
    ]
    return build_problem_ir(
        workload_key="solver_fixture",
        workload_type="buyer_allocation",
        source_schema_version="fixture.v1",
        variable_type="BINARY",
        variables=variables,
        objective={
            "sense": "MAXIMIZE",
            "linear": {row["variable"]: index + 1 for index, row in enumerate(variables)},
            "quadratic": {},
        },
        constraints=[],
        representations=("QUBO", "CQM"),
        cost_budget_minor_units=cost_budget_minor_units,
        time_budget_ms=time_budget_ms,
    )


def _runtime(**overrides):
    packet = {
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
    for section, values in overrides.items():
        packet[section].update(values)
    return packet


def test_small_supported_problem_prefers_exact_classical_reference():
    route = route_solver(_problem(3), runtime=_runtime(), exact_variable_limit=24)

    assert route["primary_solver"] == "classical_exact_reference"
    assert route["primary_reference_quality"] == "OPTIMAL_REFERENCE"
    assert route["quantum_advantage_claimed"] is False


def test_large_problem_falls_back_to_safe_builtin_without_time_budget():
    route = route_solver(_problem(25), runtime=_runtime(), exact_variable_limit=24)

    assert route["primary_solver"] == "classical_greedy_reference"
    assert route["queue_class"] == "optimization:scalable"
    assert route["production_solver_origin"] == "empire_owned"
    assert route["third_party_runtime_allowed"] is False
    assert None not in route["fallback_chain"]


def test_large_bounded_problem_prefers_empire_branch_bound():
    route = route_solver(
        _problem(25, time_budget_ms=1000),
        runtime=_runtime(),
        exact_variable_limit=24,
    )

    assert route["primary_solver"] == "empire_branch_bound"
    assert route["primary_reference_quality"] == "BOUNDED_EXACT_OR_INCUMBENT"
    assert route["routing_reason"] == (
        "empire_owned_scalable_binary_linear_solver"
    )
    assert "ortools_cp_sat" not in route["fallback_chain"]


def test_third_party_solver_lanes_are_market_reference_only():
    runtime = _runtime(
        packages={"qiskit": True, "ortools": True},
        provider_flags={"ibm_quantum": True},
        empire_adapters={"ibm_qaoa": True, "ortools_cp_sat": True},
    )

    route = route_solver(
        _problem(
            25,
            cost_budget_minor_units=100,
            time_budget_ms=5000,
        ),
        runtime=runtime,
        exact_variable_limit=24,
        allow_external_qpu_benchmark=True,
    )

    assert route["primary_solver"] == "empire_branch_bound"
    ibm = next(
        row for row in route["benchmark_lanes"]
        if row["solver"] == "ibm_qaoa"
    )
    ortools = next(
        row for row in route["benchmark_lanes"]
        if row["solver"] == "ortools_cp_sat"
    )
    assert ibm["runnable"] is False
    assert ibm["purpose"] == "market_reference_only"
    assert "third_party_runtime_not_allowed" in ibm["blockers"]
    assert ortools["runnable"] is False
    assert ortools["purpose"] == "market_reference_only"
    assert "third_party_runtime_not_allowed" in ortools["blockers"]
    assert route["third_party_runtime_allowed"] is False
    assert route["production_solver_origin"] == "empire_owned"
