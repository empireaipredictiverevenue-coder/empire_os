import pytest

from empire_os.optimization_benchmark_ledger import (
    build_solver_run_evidence,
    compare_solver_runs,
    summarize_repeatability,
)
from empire_os.optimization_problem_factory import build_problem_ir


def _problem():
    return build_problem_ir(
        workload_key="benchmark_fixture",
        workload_type="buyer_allocation",
        source_schema_version="fixture.v1",
        variable_type="BINARY",
        variables=[
            {"variable": "x::1", "evidence_refs": ["evidence:1"]}
        ],
        objective={
            "sense": "MAXIMIZE",
            "linear": {"x::1": 100},
            "quadratic": {},
        },
        constraints=[],
        representations=("QUBO",),
    )


def _run(problem, *, solver, objective, wall, cost=None, ref="run:1"):
    return build_solver_run_evidence(
        problem=problem,
        solver=solver,
        solver_family="classical" if solver == "exact" else "quantum_candidate",
        hardware_class="cpu" if solver == "exact" else "qpu_simulator",
        objective_value=objective,
        constraints_satisfied=True,
        wall_clock_ms=wall,
        compute_cost_minor_units=cost,
        observed_at="2026-10-02T20:00:00+00:00",
        run_ref=ref,
        external=solver != "exact",
    )


def test_benchmark_preserves_unknown_compute_cost():
    packet = _run(_problem(), solver="candidate", objective=100, wall=10)

    assert packet["compute_cost_minor_units"] is None
    assert packet["compute_cost_known"] is False
    assert packet["quantum_advantage_claimed"] is False


def test_compare_requires_same_problem_and_records_quality_latency_cost():
    problem = _problem()
    baseline = _run(
        problem,
        solver="exact",
        objective=100,
        wall=20,
        cost=2,
        ref="baseline",
    )
    candidate = _run(
        problem,
        solver="candidate",
        objective=100,
        wall=10,
        cost=3,
        ref="candidate",
    )

    review = compare_solver_runs(
        problem=problem,
        baseline=baseline,
        candidate=candidate,
    )

    assert review["matches_or_beats_reference"] is True
    assert review["speedup_ratio"] == 2.0
    assert review["compute_cost_delta_minor_units"] == 1.0
    assert review["quantum_advantage_claimed"] is False
    assert review["production_promotion_ready"] is False


def test_compare_rejects_mismatched_problem_fingerprint():
    problem = _problem()
    other = dict(problem)
    other["problem_fingerprint"] = "different"
    baseline = _run(problem, solver="exact", objective=100, wall=20)
    candidate = _run(other, solver="candidate", objective=100, wall=10)

    with pytest.raises(ValueError, match="candidate problem fingerprint mismatch"):
        compare_solver_runs(
            problem=problem,
            baseline=baseline,
            candidate=candidate,
        )


def test_repeatability_requires_multiple_same_identity_runs():
    problem = _problem()
    runs = [
        _run(
            problem,
            solver="candidate",
            objective=100 + index,
            wall=10 + index,
            ref=f"run:{index}",
        )
        for index in range(3)
    ]

    review = summarize_repeatability(runs)

    assert review["status"] == "AVAILABLE"
    assert review["run_count"] == 3
    assert review["all_runs_feasible"] is True
    assert review["repeatability_evidence_available"] is True
    assert review["quantum_advantage_claimed"] is False
