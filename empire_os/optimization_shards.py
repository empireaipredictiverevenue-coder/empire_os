"""Safe horizontal shard materialization and Empire-owned execution.

Only decomposition plans proven independent by the canonical planner may be
executed as parallel shards. Cross-partition/global constraints fail closed and
require a coordinator; they are never silently dropped.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from typing import Any, Mapping

from empire_os.optimization_problem_factory import (
    build_decomposition_plan,
    build_problem_ir,
    validate_problem_integrity,
)


SCHEMA_VERSION = "empire.optimization.sharded-execution.v1"


def _status(packet: Mapping[str, Any]) -> str:
    return str(packet.get("status") or "").strip().upper()


def materialize_independent_shards(
    problem: Mapping[str, Any],
    decomposition: Mapping[str, Any],
) -> dict[str, Any]:
    """Create immutable subproblems only from a proven independent plan."""
    if _status(problem) != "AVAILABLE":
        return {
            "schema_version": "empire.optimization.shards.v1",
            "status": "UNAVAILABLE",
            "reason": "optimization_problem_unavailable",
            "execution_authority": "none",
        }
    if decomposition.get("strategy") != "independent_shards":
        return {
            "schema_version": "empire.optimization.shards.v1",
            "status": "UNAVAILABLE",
            "reason": "independent_shard_plan_required",
            "decomposition_strategy": decomposition.get("strategy"),
            "execution_authority": "none",
        }
    if decomposition.get("independent_shard_execution_safe") is not True:
        return {
            "schema_version": "empire.optimization.shards.v1",
            "status": "UNAVAILABLE",
            "reason": "independent_shard_safety_not_proven",
            "execution_authority": "none",
        }

    objective = dict(problem.get("objective") or {})
    if dict(objective.get("quadratic") or {}):
        return {
            "schema_version": "empire.optimization.shards.v1",
            "status": "UNAVAILABLE",
            "reason": "quadratic_cross_shard_review_required",
            "execution_authority": "none",
        }

    variables_by_name = {
        str(row.get("variable")): dict(row)
        for row in (problem.get("variables") or ())
        if isinstance(row, Mapping) and str(row.get("variable") or "")
    }
    constraints = [
        dict(row)
        for row in (problem.get("constraints") or ())
        if isinstance(row, Mapping)
    ]
    constant_constraints = [
        str(row.get("name") or "unnamed")
        for row in constraints
        if not dict(row.get("coefficients") or {})
    ]
    if constant_constraints:
        return {
            "schema_version": "empire.optimization.shards.v1",
            "status": "UNAVAILABLE",
            "reason": "constant_constraint_requires_global_review",
            "constraints": sorted(constant_constraints),
            "execution_authority": "none",
        }

    shards: list[dict[str, Any]] = []
    partitions = dict(decomposition.get("partitions") or {})
    for partition_key, variable_names_raw in sorted(partitions.items()):
        variable_names = {
            str(name)
            for name in (variable_names_raw or ())
        }
        shard_variables = [
            variables_by_name[name]
            for name in sorted(variable_names)
            if name in variables_by_name
        ]
        if len(shard_variables) != len(variable_names):
            return {
                "schema_version": "empire.optimization.shards.v1",
                "status": "UNAVAILABLE",
                "reason": "decomposition_references_unknown_variable",
                "partition_key": partition_key,
                "execution_authority": "none",
            }

        shard_constraints: list[dict[str, Any]] = []
        for constraint in constraints:
            coefficient_names = {
                str(name)
                for name in dict(
                    constraint.get("coefficients") or {}
                )
            }
            if coefficient_names & variable_names:
                if not coefficient_names <= variable_names:
                    return {
                        "schema_version": "empire.optimization.shards.v1",
                        "status": "UNAVAILABLE",
                        "reason": "cross_partition_constraint_detected_during_materialization",
                        "constraint": constraint.get("name"),
                        "execution_authority": "none",
                    }
                shard_constraints.append(constraint)

        linear = dict(objective.get("linear") or {})
        shard_objective = {
            **objective,
            "linear": {
                name: value
                for name, value in linear.items()
                if str(name) in variable_names
            },
            "quadratic": {},
        }
        shard = build_problem_ir(
            workload_key=(
                f"{problem.get('workload_key')}::partition::{partition_key}"
            ),
            workload_type=str(problem.get("workload_type") or ""),
            source_schema_version=str(problem.get("source_schema_version") or ""),
            variable_type=str(problem.get("variable_type") or ""),
            variables=shard_variables,
            objective=shard_objective,
            constraints=shard_constraints,
            tenant_id=problem.get("tenant_id"),
            time_budget_ms=problem.get("time_budget_ms"),
            cost_budget_minor_units=problem.get(
                "cost_budget_minor_units"
            ),
            representations=tuple(problem.get("representations") or ()),
            metadata={
                **dict(problem.get("metadata") or {}),
                "parent_problem_fingerprint": problem.get(
                    "problem_fingerprint"
                ),
                "partition_key": partition_key,
                "independent_shard": True,
            },
        )
        shards.append(shard)

    return {
        "schema_version": "empire.optimization.shards.v1",
        "status": "AVAILABLE",
        "parent_problem_fingerprint": problem.get("problem_fingerprint"),
        "shard_count": len(shards),
        "shards": shards,
        "independent_shard_execution_safe": True,
        "execution_authority": "none",
    }


def solve_partitioned_cp_sat(
    problem: Mapping[str, Any],
    *,
    max_variables_per_shard: int = 5000,
    partition_field: str = "partition_key",
    max_parallel_workers: int = 4,
    cp_sat_workers_per_shard: int = 1,
) -> dict[str, Any]:
    """Market-reference only: solve shards with optional OR-Tools CP-SAT."""
    from empire_os.solver_adapters.ortools_cp_sat import solve_cp_sat

    if max_parallel_workers <= 0:
        raise ValueError("max_parallel_workers must be positive")
    if cp_sat_workers_per_shard <= 0:
        raise ValueError("cp_sat_workers_per_shard must be positive")
    parallel_workers = min(int(max_parallel_workers), 16)

    integrity = validate_problem_integrity(problem)
    if _status(integrity) != "AVAILABLE":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "optimization_problem_integrity_failed",
            "integrity": integrity,
            "execution_authority": "none",
        }

    decomposition = build_decomposition_plan(
        problem,
        max_variables_per_shard=max_variables_per_shard,
        partition_field=partition_field,
    )
    strategy = decomposition.get("strategy")

    if strategy == "single_worker":
        result = solve_cp_sat(
            problem,
            max_workers=cp_sat_workers_per_shard,
        )
        return {
            "schema_version": SCHEMA_VERSION,
            "status": result.get("status"),
            "strategy": "single_worker",
            "problem_fingerprint": problem.get("problem_fingerprint"),
            "decomposition": decomposition,
            "selected_variables": list(
                result.get("selected_variables") or []
            ),
            "objective_value": result.get("objective_value"),
            "constraints_satisfied": result.get(
                "constraints_satisfied"
            ),
            "wall_clock_ms": result.get("wall_clock_ms"),
            "shard_count": 1,
            "shard_results": [result],
            "compute_cost_minor_units": result.get(
                "compute_cost_minor_units"
            ),
            "compute_cost_known": result.get(
                "compute_cost_known"
            ) is True,
            "external_solver_called": False,
            "production_promotion_ready": False,
            "execution_authority": "none",
        }

    if strategy != "independent_shards":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "global_coordinator_required",
            "problem_fingerprint": problem.get("problem_fingerprint"),
            "decomposition": decomposition,
            "global_constraint_reconciliation_required": True,
            "external_solver_called": False,
            "execution_authority": "none",
        }

    materialized = materialize_independent_shards(
        problem,
        decomposition,
    )
    if _status(materialized) != "AVAILABLE":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": materialized.get("reason"),
            "decomposition": decomposition,
            "materialization": materialized,
            "execution_authority": "none",
        }

    shards = list(materialized.get("shards") or [])
    started = time.perf_counter()
    results_by_fingerprint: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(
        max_workers=min(parallel_workers, max(1, len(shards)))
    ) as pool:
        futures = {
            pool.submit(
                solve_cp_sat,
                shard,
                max_workers=cp_sat_workers_per_shard,
            ): shard
            for shard in shards
        }
        for future in as_completed(futures):
            shard = futures[future]
            result = future.result()
            results_by_fingerprint[
                str(shard.get("problem_fingerprint"))
            ] = result
    wall_clock_ms = (time.perf_counter() - started) * 1000.0

    ordered_results = [
        results_by_fingerprint[str(shard.get("problem_fingerprint"))]
        for shard in shards
    ]
    failures = [
        result
        for result in ordered_results
        if result.get("status") != "AVAILABLE"
        or result.get("constraints_satisfied") is not True
    ]
    if failures:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "one_or_more_shards_failed",
            "problem_fingerprint": problem.get("problem_fingerprint"),
            "shard_count": len(shards),
            "failed_shard_count": len(failures),
            "shard_results": ordered_results,
            "wall_clock_ms": round(wall_clock_ms, 6),
            "external_solver_called": False,
            "execution_authority": "none",
        }

    selected = sorted({
        variable
        for result in ordered_results
        for variable in (result.get("selected_variables") or ())
    })
    objective_value = sum(
        float(result.get("objective_value") or 0.0)
        for result in ordered_results
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE",
        "strategy": "independent_shards",
        "problem_fingerprint": problem.get("problem_fingerprint"),
        "decomposition": decomposition,
        "shard_count": len(shards),
        "parallel_worker_limit": parallel_workers,
        "cp_sat_workers_per_shard": int(cp_sat_workers_per_shard),
        "selected_variables": selected,
        "selected_count": len(selected),
        "objective_value": round(objective_value, 8),
        "constraints_satisfied": True,
        "shard_results": ordered_results,
        "wall_clock_ms": round(wall_clock_ms, 6),
        "compute_cost_minor_units": None,
        "compute_cost_known": False,
        "external_solver_called": False,
        "production_promotion_ready": False,
        "execution_authority": "none",
    }


def solve_partitioned_empire_branch_bound(
    problem: Mapping[str, Any],
    *,
    max_variables_per_shard: int = 5000,
    partition_field: str = "partition_key",
    max_parallel_workers: int = 4,
    max_nodes_per_shard: int = 2_000_000,
) -> dict[str, Any]:
    """Solve one problem or proven-independent shards with Empire-owned B&B."""
    from empire_os.solver_adapters.empire_branch_bound import (
        solve_empire_branch_bound,
    )

    if max_parallel_workers <= 0:
        raise ValueError("max_parallel_workers must be positive")
    if max_nodes_per_shard <= 0:
        raise ValueError("max_nodes_per_shard must be positive")
    parallel_workers = min(int(max_parallel_workers), 16)

    integrity = validate_problem_integrity(problem)
    if _status(integrity) != "AVAILABLE":
        return {
            "schema_version": "empire.optimization.empire-sharded-execution.v1",
            "status": "UNAVAILABLE",
            "reason": "optimization_problem_integrity_failed",
            "integrity": integrity,
            "execution_authority": "none",
        }

    decomposition = build_decomposition_plan(
        problem,
        max_variables_per_shard=max_variables_per_shard,
        partition_field=partition_field,
    )
    strategy = decomposition.get("strategy")

    if strategy == "single_worker":
        result = solve_empire_branch_bound(
            problem,
            max_nodes=max_nodes_per_shard,
        )
        return {
            "schema_version": "empire.optimization.empire-sharded-execution.v1",
            "status": result.get("status"),
            "strategy": "single_worker",
            "problem_fingerprint": problem.get("problem_fingerprint"),
            "decomposition": decomposition,
            "selected_variables": list(
                result.get("selected_variables") or []
            ),
            "objective_value": result.get("objective_value"),
            "constraints_satisfied": result.get(
                "constraints_satisfied"
            ),
            "wall_clock_ms": result.get("wall_clock_ms"),
            "shard_count": 1,
            "shard_results": [result],
            "all_shards_optimal": (
                result.get("optimal_for_normalized_problem") is True
            ),
            "solver": "empire_branch_bound",
            "solver_origin": "empire_owned",
            "third_party_runtime_dependency": False,
            "compute_cost_minor_units": None,
            "compute_cost_known": False,
            "external_solver_called": False,
            "production_promotion_ready": False,
            "execution_authority": "none",
        }

    if strategy != "independent_shards":
        return {
            "schema_version": "empire.optimization.empire-sharded-execution.v1",
            "status": "UNAVAILABLE",
            "reason": "global_coordinator_required",
            "problem_fingerprint": problem.get("problem_fingerprint"),
            "decomposition": decomposition,
            "global_constraint_reconciliation_required": True,
            "external_solver_called": False,
            "execution_authority": "none",
        }

    materialized = materialize_independent_shards(
        problem,
        decomposition,
    )
    if _status(materialized) != "AVAILABLE":
        return {
            "schema_version": "empire.optimization.empire-sharded-execution.v1",
            "status": "UNAVAILABLE",
            "reason": materialized.get("reason"),
            "decomposition": decomposition,
            "materialization": materialized,
            "execution_authority": "none",
        }

    shards = list(materialized.get("shards") or [])
    started = time.perf_counter()
    results_by_fingerprint: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(
        max_workers=min(parallel_workers, max(1, len(shards)))
    ) as pool:
        futures = {
            pool.submit(
                solve_empire_branch_bound,
                shard,
                max_nodes=max_nodes_per_shard,
            ): shard
            for shard in shards
        }
        for future in as_completed(futures):
            shard = futures[future]
            result = future.result()
            results_by_fingerprint[
                str(shard.get("problem_fingerprint"))
            ] = result
    wall_clock_ms = (time.perf_counter() - started) * 1000.0

    ordered_results = [
        results_by_fingerprint[str(shard.get("problem_fingerprint"))]
        for shard in shards
    ]
    failures = [
        result
        for result in ordered_results
        if result.get("status") != "AVAILABLE"
        or result.get("constraints_satisfied") is not True
    ]
    if failures:
        return {
            "schema_version": "empire.optimization.empire-sharded-execution.v1",
            "status": "UNAVAILABLE",
            "reason": "one_or_more_shards_failed",
            "problem_fingerprint": problem.get("problem_fingerprint"),
            "shard_count": len(shards),
            "failed_shard_count": len(failures),
            "shard_results": ordered_results,
            "wall_clock_ms": round(wall_clock_ms, 6),
            "external_solver_called": False,
            "execution_authority": "none",
        }

    selected = sorted({
        variable
        for result in ordered_results
        for variable in (result.get("selected_variables") or ())
    })
    objective_value = sum(
        float(result.get("objective_value") or 0.0)
        for result in ordered_results
    )
    all_optimal = all(
        result.get("optimal_for_normalized_problem") is True
        for result in ordered_results
    )

    return {
        "schema_version": "empire.optimization.empire-sharded-execution.v1",
        "status": "AVAILABLE",
        "strategy": "independent_shards",
        "problem_fingerprint": problem.get("problem_fingerprint"),
        "decomposition": decomposition,
        "shard_count": len(shards),
        "parallel_worker_limit": parallel_workers,
        "selected_variables": selected,
        "selected_count": len(selected),
        "objective_value": round(objective_value, 8),
        "constraints_satisfied": True,
        "shard_results": ordered_results,
        "all_shards_optimal": all_optimal,
        "solver": "empire_branch_bound",
        "solver_origin": "empire_owned",
        "third_party_runtime_dependency": False,
        "wall_clock_ms": round(wall_clock_ms, 6),
        "compute_cost_minor_units": None,
        "compute_cost_known": False,
        "external_solver_called": False,
        "production_promotion_ready": False,
        "execution_authority": "none",
    }
