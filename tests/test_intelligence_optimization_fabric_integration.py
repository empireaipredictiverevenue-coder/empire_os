from empire_os.hybrid_optimization import solve_allocation_classical_greedy
from empire_os.optimization_benchmark_ledger import (
    build_solver_run_evidence,
    compare_solver_runs,
)
from empire_os.optimization_problem_factory import compile_allocation_problem
from empire_os.quantum_optimization import (
    build_allocation_optimization_problem,
    solve_allocation_classical_exact,
)
from empire_os.solver_intelligence import route_solver


def test_buyer_allocation_flows_through_v2_factory_router_and_benchmark():
    source = build_allocation_optimization_problem(
        options=[
            {
                "prospect_id": "p1",
                "buyer_id": "b1",
                "expected_value_cents": 2000,
                "evidence_refs": ["ev:p1-b1"],
            },
            {
                "prospect_id": "p1",
                "buyer_id": "b2",
                "expected_value_cents": 1500,
                "evidence_refs": ["ev:p1-b2"],
            },
            {
                "prospect_id": "p2",
                "buyer_id": "b1",
                "expected_value_cents": 1200,
                "evidence_refs": ["ev:p2-b1"],
            },
        ],
        buyer_capacities={"b1": 1, "b2": 1},
    )
    ir = compile_allocation_problem(source, tenant_id="tenant-a")
    route = route_solver(ir)

    assert ir["status"] == "AVAILABLE"
    assert ir["tenant_id"] == "tenant-a"
    assert route["primary_solver"] == "classical_exact_reference"

    exact = solve_allocation_classical_exact(source)
    greedy = solve_allocation_classical_greedy(source)

    baseline = build_solver_run_evidence(
        problem=ir,
        solver="classical_exact_reference",
        solver_family="classical_exact",
        hardware_class="cpu",
        objective_value=exact["objective_value_cents"],
        constraints_satisfied=True,
        wall_clock_ms=1,
        observed_at="2026-10-02T20:00:00+00:00",
        run_ref="integration:exact",
    )
    candidate = build_solver_run_evidence(
        problem=ir,
        solver="classical_greedy_reference",
        solver_family="classical_heuristic",
        hardware_class="cpu",
        objective_value=greedy["objective_value_cents"],
        constraints_satisfied=True,
        wall_clock_ms=1,
        observed_at="2026-10-02T20:00:01+00:00",
        run_ref="integration:greedy",
    )
    comparison = compare_solver_runs(
        problem=ir,
        baseline=baseline,
        candidate=candidate,
    )

    assert comparison["problem_fingerprint"] == ir["problem_fingerprint"]
    assert comparison["quantum_advantage_claimed"] is False
    assert comparison["execution_authority"] == "none"
