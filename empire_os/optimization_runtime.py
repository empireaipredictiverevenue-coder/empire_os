"""Governed OBSERVE runtime for Empire Intelligence Optimization Fabric V2."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from empire_os.optimization_shards import (
    solve_partitioned_empire_branch_bound,
)
from empire_os.optimization_benchmark_ledger import (
    build_solver_run_evidence,
    compare_solver_runs,
)
from empire_os.solver_adapters.exact_binary import (
    DEFAULT_MAX_VARIABLES,
    solve_exact_binary,
)
from empire_os.solver_adapters.greedy_binary import solve_greedy_binary
from empire_os.solver_adapters.empire_branch_bound import (
    solve_empire_branch_bound,
)


SCHEMA_VERSION = "empire.optimization.runtime.v1"


def _status(packet: Mapping[str, Any]) -> str:
    return str(packet.get("status") or "").strip().upper()


def execute_primary_solver(
    fabric_plan: Mapping[str, Any],
    *,
    exact_variable_limit: int = DEFAULT_MAX_VARIABLES,
    max_workers: int = 1,
) -> dict[str, Any]:
    """Run only the solver selected by the governed router, in recommendation mode."""
    if _status(fabric_plan) != "AVAILABLE":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "fabric_plan_unavailable",
            "execution_authority": "none",
        }
    if fabric_plan.get("solver_execution_ready") is not True:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "solver_execution_not_ready",
            "primary_solver": fabric_plan.get("primary_solver"),
            "execution_authority": "none",
        }

    problem = fabric_plan.get("problem")
    if not isinstance(problem, Mapping):
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "optimization_problem_missing",
            "execution_authority": "none",
        }

    solver = str(fabric_plan.get("primary_solver") or "").strip()
    if solver == "classical_exact_reference":
        result = solve_exact_binary(
            problem,
            max_variables=exact_variable_limit,
        )
    elif solver == "empire_branch_bound":
        decomposition = fabric_plan.get("decomposition")
        decomposition = (
            decomposition
            if isinstance(decomposition, Mapping)
            else {}
        )
        if decomposition.get("strategy") == "independent_shards":
            result = solve_partitioned_empire_branch_bound(
                problem,
                max_variables_per_shard=int(
                    fabric_plan.get("max_variables_per_shard") or 5000
                ),
                max_parallel_workers=max_workers,
            )
        else:
            result = solve_empire_branch_bound(problem)
    elif solver == "classical_greedy_reference":
        result = solve_greedy_binary(problem)
    else:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "primary_solver_adapter_not_implemented",
            "primary_solver": solver or None,
            "execution_authority": "none",
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "status": result.get("status"),
        "problem_fingerprint": problem.get("problem_fingerprint"),
        "primary_solver": solver,
        "result": result,
        "recommendation_only": True,
        "production_promotion_ready": False,
        "external_action_performed": False,
        "quantum_advantage_claimed": False,
        "execution_authority": "none",
    }


def compare_cp_sat_with_exact_reference(
    fabric_plan: Mapping[str, Any],
    *,
    exact_variable_limit: int = DEFAULT_MAX_VARIABLES,
    cp_sat_max_workers: int = 1,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Market-reference benchmark: CP-SAT vs Empire exact on one problem."""
    if _status(fabric_plan) != "AVAILABLE":
        return {
            "schema_version": "empire.optimization.reference-comparison.v1",
            "status": "UNAVAILABLE",
            "reason": "fabric_plan_unavailable",
            "execution_authority": "none",
        }
    problem = fabric_plan.get("problem")
    if not isinstance(problem, Mapping):
        return {
            "schema_version": "empire.optimization.reference-comparison.v1",
            "status": "UNAVAILABLE",
            "reason": "optimization_problem_missing",
            "execution_authority": "none",
        }

    exact = solve_exact_binary(
        problem,
        max_variables=exact_variable_limit,
    )
    from empire_os.solver_adapters.ortools_cp_sat import solve_cp_sat

    cp_sat = solve_cp_sat(
        problem,
        max_workers=cp_sat_max_workers,
    )
    if _status(exact) != "AVAILABLE" or _status(cp_sat) != "AVAILABLE":
        return {
            "schema_version": "empire.optimization.reference-comparison.v1",
            "status": "UNAVAILABLE",
            "reason": "one_or_more_reference_solvers_unavailable",
            "exact_status": exact.get("status"),
            "cp_sat_status": cp_sat.get("status"),
            "exact_reason": exact.get("reason"),
            "cp_sat_reason": cp_sat.get("reason"),
            "execution_authority": "none",
        }

    timestamp = observed_at or datetime.now(timezone.utc).isoformat()
    exact_run = build_solver_run_evidence(
        problem=problem,
        solver="classical_exact_binary_ir",
        solver_family="classical_exact",
        hardware_class="cpu",
        objective_value=exact["objective_value"],
        constraints_satisfied=exact["constraints_satisfied"],
        wall_clock_ms=exact["wall_clock_ms"],
        compute_cost_minor_units=None,
        observed_at=timestamp,
        run_ref="runtime:exact_binary",
        external=False,
    )
    cp_sat_run = build_solver_run_evidence(
        problem=problem,
        solver="ortools_cp_sat",
        solver_family="classical_cp_sat",
        hardware_class="cpu",
        objective_value=cp_sat["objective_value"],
        constraints_satisfied=cp_sat["constraints_satisfied"],
        wall_clock_ms=cp_sat["wall_clock_ms"],
        compute_cost_minor_units=None,
        provider="google_or_tools",
        observed_at=timestamp,
        run_ref="runtime:ortools_cp_sat",
        external=False,
    )
    comparison = compare_solver_runs(
        problem=problem,
        baseline=exact_run,
        candidate=cp_sat_run,
    )
    return {
        "schema_version": "empire.optimization.reference-comparison.v1",
        "status": "AVAILABLE",
        "problem_fingerprint": problem.get("problem_fingerprint"),
        "exact": exact,
        "cp_sat": cp_sat,
        "comparison": comparison,
        "same_problem_verified": True,
        "production_promotion_ready": False,
        "quantum_advantage_claimed": False,
        "execution_authority": "none",
    }


def compare_local_qubo_with_exact_reference(
    fabric_plan: Mapping[str, Any],
    *,
    exact_variable_limit: int = DEFAULT_MAX_VARIABLES,
    num_reads: int = 100,
    num_sweeps: int = 1000,
    seed: int = 1729,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Benchmark local quantum-inspired annealing against the exact reference."""
    from empire_os.optimization_qubo import build_safe_qubo
    from empire_os.solver_adapters.empire_annealing import (
        solve_empire_annealing,
    )

    if _status(fabric_plan) != "AVAILABLE":
        return {
            "schema_version": "empire.optimization.local-qubo-comparison.v1",
            "status": "UNAVAILABLE",
            "reason": "fabric_plan_unavailable",
            "execution_authority": "none",
        }
    problem = fabric_plan.get("problem")
    if not isinstance(problem, Mapping):
        return {
            "schema_version": "empire.optimization.local-qubo-comparison.v1",
            "status": "UNAVAILABLE",
            "reason": "optimization_problem_missing",
            "execution_authority": "none",
        }

    exact = solve_exact_binary(
        problem,
        max_variables=exact_variable_limit,
    )
    qubo = build_safe_qubo(problem)
    annealed = solve_empire_annealing(
        qubo,
        num_reads=num_reads,
        sweeps_per_read=num_sweeps,
        seed=seed,
    )
    if (
        _status(exact) != "AVAILABLE"
        or _status(qubo) != "AVAILABLE"
        or _status(annealed) != "AVAILABLE"
    ):
        return {
            "schema_version": "empire.optimization.local-qubo-comparison.v1",
            "status": "UNAVAILABLE",
            "reason": "one_or_more_benchmark_components_unavailable",
            "exact_status": exact.get("status"),
            "exact_reason": exact.get("reason"),
            "qubo_status": qubo.get("status"),
            "qubo_reason": qubo.get("reason"),
            "candidate_status": annealed.get("status"),
            "candidate_reason": annealed.get("reason"),
            "production_promotion_ready": False,
            "quantum_advantage_claimed": False,
            "execution_authority": "none",
        }

    timestamp = observed_at or datetime.now(timezone.utc).isoformat()
    exact_run = build_solver_run_evidence(
        problem=problem,
        solver="classical_exact_binary_ir",
        solver_family="classical_exact",
        hardware_class="cpu",
        objective_value=exact["objective_value"],
        constraints_satisfied=exact["constraints_satisfied"],
        wall_clock_ms=exact["wall_clock_ms"],
        compute_cost_minor_units=None,
        observed_at=timestamp,
        run_ref="runtime:exact_binary",
        external=False,
    )
    candidate_run = build_solver_run_evidence(
        problem=problem,
        solver="empire_annealing",
        solver_family="empire_quantum_inspired_annealing",
        hardware_class="cpu",
        objective_value=annealed["objective_value"],
        constraints_satisfied=annealed["constraints_satisfied"],
        wall_clock_ms=annealed["wall_clock_ms"],
        compute_cost_minor_units=None,
        provider="empire_os",
        observed_at=timestamp,
        run_ref="runtime:empire_annealing",
        external=False,
    )
    comparison = compare_solver_runs(
        problem=problem,
        baseline=exact_run,
        candidate=candidate_run,
    )
    return {
        "schema_version": "empire.optimization.local-qubo-comparison.v1",
        "status": "AVAILABLE",
        "problem_fingerprint": problem.get("problem_fingerprint"),
        "exact": exact,
        "qubo": qubo,
        "candidate": annealed,
        "comparison": comparison,
        "same_problem_verified": True,
        "qpu_called": False,
        "quantum_inspired_only": True,
        "production_promotion_ready": False,
        "quantum_advantage_claimed": False,
        "execution_authority": "none",
    }
