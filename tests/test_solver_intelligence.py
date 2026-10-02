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


def test_large_problem_falls_back_to_safe_builtin_without_adapter():
    route = route_solver(_problem(25), runtime=_runtime(), exact_variable_limit=24)

    assert route["primary_solver"] == "classical_greedy_reference"
    assert route["queue_class"] == "optimization:scalable"
    assert None not in route["fallback_chain"]


def test_qpu_lane_requires_both_explicit_route_authority_and_provider_enable():
    runtime = _runtime(
        packages={"qiskit": True},
        provider_flags={"ibm_quantum": True},
        empire_adapters={"ibm_qaoa": True},
    )

    blocked = route_solver(
        _problem(3),
        runtime=runtime,
        allow_external_qpu_benchmark=False,
    )
    ibm = next(
        row for row in blocked["benchmark_lanes"]
        if row["solver"] == "ibm_qaoa"
    )
    assert ibm["runnable"] is False
    assert "external_qpu_benchmark_not_authorized_for_route" in ibm["blockers"]

    route_only = route_solver(
        _problem(3),
        runtime=runtime,
        allow_external_qpu_benchmark=True,
    )
    ibm = next(
        row for row in route_only["benchmark_lanes"]
        if row["solver"] == "ibm_qaoa"
    )
    assert ibm["runnable"] is False
    assert "cost_budget_required_for_external_solver" in ibm["blockers"]

    budgeted_cost_only = route_solver(
        _problem(3, cost_budget_minor_units=100),
        runtime=runtime,
        allow_external_qpu_benchmark=True,
    )
    ibm = next(
        row for row in budgeted_cost_only["benchmark_lanes"]
        if row["solver"] == "ibm_qaoa"
    )
    assert ibm["runnable"] is False
    assert "time_budget_required_for_external_solver" in ibm["blockers"]

    allowed = route_solver(
        _problem(
            3,
            cost_budget_minor_units=100,
            time_budget_ms=5000,
        ),
        runtime=runtime,
        allow_external_qpu_benchmark=True,
    )
    ibm = next(
        row for row in allowed["benchmark_lanes"]
        if row["solver"] == "ibm_qaoa"
    )
    assert ibm["runnable"] is True
    assert allowed["production_promotion_ready"] is False
