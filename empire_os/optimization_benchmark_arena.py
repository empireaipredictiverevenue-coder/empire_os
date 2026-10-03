"""Empire-owned optimization Benchmark Arena.

Default runs contain only Empire-owned solver implementations. Optional market
references may be invoked explicitly for competitive lab benchmarking, but are
kept in a separate evidence lane and never feed production solver policy.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from empire_os.optimization_benchmark_ledger import (
    build_solver_run_evidence,
    compare_solver_runs,
)
from empire_os.optimization_qubo import build_safe_qubo
from empire_os.solver_adapters.empire_annealing import (
    solve_empire_annealing,
)
from empire_os.solver_adapters.empire_branch_bound import (
    solve_empire_branch_bound,
)
from empire_os.solver_adapters.empire_parallel_tempering import (
    solve_empire_parallel_tempering,
)
from empire_os.solver_adapters.empire_qaoa_simulator import (
    solve_empire_qaoa_simulator,
)
from empire_os.solver_adapters.empire_tabu import solve_empire_tabu
from empire_os.solver_adapters.exact_binary import (
    DEFAULT_MAX_VARIABLES,
    solve_exact_binary,
)


SCHEMA_VERSION = "empire.optimization.benchmark-arena.v2"


def _status(packet: Mapping[str, Any]) -> str:
    return str(packet.get("status") or "").strip().upper()


def _run_evidence(
    *,
    problem: Mapping[str, Any],
    result: Mapping[str, Any],
    observed_at: str,
    run_ref: str,
) -> dict[str, Any]:
    return build_solver_run_evidence(
        problem=problem,
        solver=str(result.get("solver") or ""),
        solver_family=str(result.get("solver_family") or ""),
        hardware_class=str(result.get("hardware_class") or "cpu"),
        objective_value=result.get("objective_value"),
        constraints_satisfied=result.get("constraints_satisfied") is True,
        wall_clock_ms=result.get("wall_clock_ms"),
        compute_cost_minor_units=result.get("compute_cost_minor_units"),
        provider=(
            str(result.get("provider"))
            if result.get("provider") is not None
            else "empire_os"
        ),
        observed_at=observed_at,
        run_ref=run_ref,
        external=False,
    )


def _market_reference_runs(
    problem: Mapping[str, Any],
    *,
    cp_sat_workers: int,
    annealing_num_reads: int,
    annealing_num_sweeps: int,
    annealing_seed: int,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Explicitly optional third-party/local market reference comparisons."""
    runs: dict[str, dict[str, Any]] = {}
    unavailable: dict[str, dict[str, Any]] = {}

    try:
        from empire_os.solver_adapters.ortools_cp_sat import solve_cp_sat

        cp_sat = solve_cp_sat(problem, max_workers=cp_sat_workers)
        if _status(cp_sat) == "AVAILABLE":
            runs["ortools_cp_sat"] = cp_sat
        else:
            unavailable["ortools_cp_sat"] = cp_sat
    except Exception as exc:  # benchmark isolation; never affects Empire lane
        unavailable["ortools_cp_sat"] = {
            "status": "UNAVAILABLE",
            "reason": "market_reference_runtime_error",
            "detail": f"{type(exc).__name__}:{exc}",
        }

    qubo = build_safe_qubo(problem)
    if _status(qubo) == "AVAILABLE":
        try:
            from empire_os.solver_adapters.dwave_local import (
                solve_simulated_annealing,
            )

            candidate = solve_simulated_annealing(
                qubo,
                num_reads=annealing_num_reads,
                num_sweeps=annealing_num_sweeps,
                seed=annealing_seed,
            )
            if _status(candidate) == "AVAILABLE":
                runs["dwave_local_simulated_annealing"] = candidate
            else:
                unavailable["dwave_local_simulated_annealing"] = candidate
        except Exception as exc:
            unavailable["dwave_local_simulated_annealing"] = {
                "status": "UNAVAILABLE",
                "reason": "market_reference_runtime_error",
                "detail": f"{type(exc).__name__}:{exc}",
            }

    return runs, unavailable


def run_benchmark_arena(
    fabric_plan: Mapping[str, Any],
    *,
    exact_variable_limit: int = DEFAULT_MAX_VARIABLES,
    branch_bound_max_nodes: int = 2_000_000,
    annealing_num_reads: int = 100,
    annealing_num_sweeps: int = 1000,
    annealing_seed: int = 1729,
    parallel_tempering_replica_count: int = 8,
    parallel_tempering_rounds: int = 80,
    qaoa_max_variables: int = 10,
    qaoa_gamma_steps: int = 9,
    qaoa_beta_steps: int = 7,
    include_market_references: bool = False,
    cp_sat_workers: int = 1,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Benchmark Empire-owned lanes on one immutable problem."""
    if _status(fabric_plan) != "AVAILABLE":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "fabric_plan_unavailable",
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

    timestamp = observed_at or datetime.now(timezone.utc).isoformat()
    runs: dict[str, dict[str, Any]] = {}
    unavailable: dict[str, dict[str, Any]] = {}

    exact = solve_exact_binary(
        problem,
        max_variables=exact_variable_limit,
    )
    if _status(exact) == "AVAILABLE":
        runs["classical_exact_binary_ir"] = exact
    else:
        unavailable["classical_exact_binary_ir"] = exact

    branch_bound = solve_empire_branch_bound(
        problem,
        max_nodes=branch_bound_max_nodes,
    )
    if _status(branch_bound) == "AVAILABLE":
        runs["empire_branch_bound"] = branch_bound
    else:
        unavailable["empire_branch_bound"] = branch_bound

    qubo = build_safe_qubo(problem)
    if _status(qubo) == "AVAILABLE":
        annealed = solve_empire_annealing(
            qubo,
            num_reads=annealing_num_reads,
            sweeps_per_read=annealing_num_sweeps,
            seed=annealing_seed,
        )
        if _status(annealed) == "AVAILABLE":
            runs["empire_annealing"] = annealed
        else:
            unavailable["empire_annealing"] = annealed

        tempered = solve_empire_parallel_tempering(
            qubo,
            replica_count=parallel_tempering_replica_count,
            rounds=parallel_tempering_rounds,
            seed=annealing_seed,
        )
        if _status(tempered) == "AVAILABLE":
            runs["empire_parallel_tempering"] = tempered
        else:
            unavailable["empire_parallel_tempering"] = tempered

        tabu = solve_empire_tabu(
            qubo,
            seed=annealing_seed,
        )
        if _status(tabu) == "AVAILABLE":
            runs["empire_tabu"] = tabu
        else:
            unavailable["empire_tabu"] = tabu

        variable_count = int(problem.get("variable_count") or 0)
        if 0 < variable_count <= qaoa_max_variables:
            qaoa = solve_empire_qaoa_simulator(
                qubo,
                max_qubits=qaoa_max_variables,
                gamma_steps=qaoa_gamma_steps,
                beta_steps=qaoa_beta_steps,
            )
            if _status(qaoa) == "AVAILABLE":
                runs["empire_qaoa_simulator"] = qaoa
            else:
                unavailable["empire_qaoa_simulator"] = qaoa
        else:
            unavailable["empire_qaoa_simulator"] = {
                "status": "UNAVAILABLE",
                "reason": "benchmark_qaoa_variable_limit",
                "variable_count": variable_count,
                "max_variables": qaoa_max_variables,
                "execution_authority": "none",
            }
    else:
        unavailable["safe_qubo"] = qubo

    if not runs:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "no_empire_solver_run_available",
            "problem_fingerprint": problem.get("problem_fingerprint"),
            "unavailable_lanes": unavailable,
            "solver_origin": "empire_owned",
            "third_party_runtime_dependency": False,
            "external_qpu_called": False,
            "quantum_advantage_claimed": False,
            "execution_authority": "none",
        }

    evidence_runs = {
        key: _run_evidence(
            problem=problem,
            result=result,
            observed_at=timestamp,
            run_ref=f"benchmark_arena:{key}",
        )
        for key, result in runs.items()
    }

    baseline_key = None
    if "classical_exact_binary_ir" in evidence_runs:
        baseline_key = "classical_exact_binary_ir"
    elif (
        "empire_branch_bound" in evidence_runs
        and runs["empire_branch_bound"].get(
            "optimal_for_normalized_problem"
        ) is True
    ):
        baseline_key = "empire_branch_bound"

    comparisons: dict[str, dict[str, Any]] = {}
    if baseline_key is not None:
        baseline = evidence_runs[baseline_key]
        for key, candidate in evidence_runs.items():
            if key == baseline_key:
                continue
            comparisons[key] = compare_solver_runs(
                problem=problem,
                baseline=baseline,
                candidate=candidate,
            )

    feasible_runs = [
        row
        for row in evidence_runs.values()
        if row.get("constraints_satisfied") is True
    ]
    objective_sense = str(
        dict(problem.get("objective") or {}).get("sense") or ""
    ).upper()
    best_observed_solver = None
    if feasible_runs:
        def rank_key(row: Mapping[str, Any]) -> tuple[float, float, str]:
            objective_value = float(row.get("objective_value") or 0.0)
            quality_key = (
                -objective_value
                if objective_sense == "MAXIMIZE"
                else objective_value
            )
            return (
                quality_key,
                float(row.get("wall_clock_ms") or 0.0),
                str(row.get("solver") or ""),
            )

        best_observed_solver = sorted(
            feasible_runs,
            key=rank_key,
        )[0].get("solver")

    market_runs: dict[str, dict[str, Any]] = {}
    market_unavailable: dict[str, dict[str, Any]] = {}
    market_comparisons: dict[str, dict[str, Any]] = {}
    if include_market_references:
        market_runs, market_unavailable = _market_reference_runs(
            problem,
            cp_sat_workers=cp_sat_workers,
            annealing_num_reads=annealing_num_reads,
            annealing_num_sweeps=annealing_num_sweeps,
            annealing_seed=annealing_seed,
        )
        if baseline_key is not None:
            baseline = evidence_runs[baseline_key]
            for key, result in market_runs.items():
                market_evidence = _run_evidence(
                    problem=problem,
                    result=result,
                    observed_at=timestamp,
                    run_ref=f"market_reference:{key}",
                )
                market_comparisons[key] = compare_solver_runs(
                    problem=problem,
                    baseline=baseline,
                    candidate=market_evidence,
                )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE",
        "problem_fingerprint": problem.get("problem_fingerprint"),
        "workload_type": problem.get("workload_type"),
        "variable_count": problem.get("variable_count"),
        "constraint_count": problem.get("constraint_count"),
        "representations": list(problem.get("representations") or []),
        "observed_at": timestamp,
        "run_count": len(evidence_runs),
        "runs": evidence_runs,
        "unavailable_lanes": unavailable,
        "baseline_solver": (
            evidence_runs[baseline_key].get("solver")
            if baseline_key is not None
            else None
        ),
        "comparisons": comparisons,
        "best_observed_solver": best_observed_solver,
        "selection_authority": "evidence_only",
        "solver_origin": "empire_owned",
        "third_party_runtime_dependency": False,
        "market_references_included": include_market_references,
        "market_reference_run_count": len(market_runs),
        "market_reference_runs": market_runs,
        "market_reference_unavailable_lanes": market_unavailable,
        "market_reference_comparisons": market_comparisons,
        "market_reference_feeds_solver_policy": False,
        "automatic_production_routing_changed": False,
        "external_qpu_called": False,
        "quantum_inspired_lane_observed": any(
            key in evidence_runs
            for key in (
                "empire_annealing",
                "empire_parallel_tempering",
                "empire_tabu",
            )
        ),
        "qaoa_simulator_lane_observed": (
            "empire_qaoa_simulator" in evidence_runs
        ),
        "production_promotion_ready": False,
        "quantum_advantage_claimed": False,
        "human_review_required": True,
        "execution_authority": "none",
    }
