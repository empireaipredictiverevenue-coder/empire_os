"""Shared governed optimization fabric for EmpireOS intelligence systems.

This module composes the canonical V2 problem factory, safe decomposition
planner and solver router into one read-only work packet. It is intentionally
provider-neutral and grants no execution, commercial, financial or accounting
authority.
"""
from __future__ import annotations

from typing import Any, Mapping

from empire_os.solver_adapters.exact_binary import DEFAULT_MAX_VARIABLES
from empire_os.optimization_problem_factory import (
    build_decomposition_plan,
    compile_action_portfolio_problem,
    compile_allocation_problem,
)
from empire_os.solver_intelligence import route_solver


SCHEMA_VERSION = "empire.intelligence_optimization_fabric.v2"


def _status(packet: Mapping[str, Any]) -> str:
    return str(packet.get("status") or "").strip().upper()


def build_optimization_fabric_plan(
    problem: Mapping[str, Any],
    *,
    runtime: Mapping[str, Any] | None = None,
    exact_variable_limit: int = DEFAULT_MAX_VARIABLES,
    max_variables_per_shard: int = 5000,
    partition_field: str = "partition_key",
    allow_external_qpu_benchmark: bool = False,
) -> dict[str, Any]:
    """Build a queueable, scalable, benchmark-only solver plan."""
    if _status(problem) != "AVAILABLE":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "optimization_problem_unavailable",
            "problem_fingerprint": problem.get("problem_fingerprint"),
            "execution_authority": "none",
        }

    decomposition = build_decomposition_plan(
        problem,
        max_variables_per_shard=max_variables_per_shard,
        partition_field=partition_field,
    )
    solver_route = route_solver(
        problem,
        runtime=runtime,
        exact_variable_limit=exact_variable_limit,
        allow_external_qpu_benchmark=allow_external_qpu_benchmark,
    )

    reps = {
        str(value).strip().upper()
        for value in (problem.get("representations") or ())
        if str(value).strip()
    }
    benchmark_lanes = list(solver_route.get("benchmark_lanes") or [])
    runnable_benchmarks = [
        row
        for row in benchmark_lanes
        if isinstance(row, Mapping) and row.get("runnable") is True
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE",
        "problem_fingerprint": problem.get("problem_fingerprint"),
        "workload_key": problem.get("workload_key"),
        "workload_type": problem.get("workload_type"),
        "tenant_id": problem.get("tenant_id"),
        "variable_count": problem.get("variable_count"),
        "constraint_count": problem.get("constraint_count"),
        "exact_variable_limit": int(exact_variable_limit),
        "max_variables_per_shard": int(max_variables_per_shard),
        "representations": sorted(reps),
        "problem": dict(problem),
        "decomposition": decomposition,
        "solver_route": solver_route,
        "primary_solver": solver_route.get("primary_solver"),
        "primary_reference_quality": solver_route.get(
            "primary_reference_quality"
        ),
        "solver_execution_ready": solver_route.get(
            "solver_execution_ready"
        ) is True,
        "qaoa_model_eligible": "QUBO" in reps,
        "cqm_model_eligible": "CQM" in reps,
        "benchmark_lane_count": len(benchmark_lanes),
        "runnable_benchmark_lane_count": len(runnable_benchmarks),
        "benchmark_evidence_required": True,
        "independent_verification_required": True,
        "global_constraint_reconciliation_required": bool(
            decomposition.get("global_constraint_reconciliation_required")
        ),
        "external_qpu_benchmark_allowed": allow_external_qpu_benchmark,
        "external_solver_called": False,
        "production_promotion_ready": False,
        "quantum_advantage_claimed": False,
        "recommendation_only": True,
        "actual_revenue": False,
        "commercial_authority": "none",
        "financial_authority": "none",
        "accounting_authority": "none",
        "execution_authority": "none",
    }


def build_allocation_fabric_plan(
    source_problem: Mapping[str, Any],
    *,
    workload_key: str = "buyer_allocation",
    tenant_id: str | None = None,
    time_budget_ms: Any = None,
    cost_budget_minor_units: Any = None,
    runtime: Mapping[str, Any] | None = None,
    exact_variable_limit: int = DEFAULT_MAX_VARIABLES,
    max_variables_per_shard: int = 5000,
    allow_external_qpu_benchmark: bool = False,
) -> dict[str, Any]:
    problem = compile_allocation_problem(
        source_problem,
        workload_key=workload_key,
        tenant_id=tenant_id,
        time_budget_ms=time_budget_ms,
        cost_budget_minor_units=cost_budget_minor_units,
    )
    return build_optimization_fabric_plan(
        problem,
        runtime=runtime,
        exact_variable_limit=exact_variable_limit,
        max_variables_per_shard=max_variables_per_shard,
        allow_external_qpu_benchmark=allow_external_qpu_benchmark,
    )


def build_action_portfolio_fabric_plan(
    source_problem: Mapping[str, Any],
    *,
    workload_key: str = "predictive_action_portfolio",
    tenant_id: str | None = None,
    time_budget_ms: Any = None,
    cost_budget_minor_units: Any = None,
    runtime: Mapping[str, Any] | None = None,
    exact_variable_limit: int = DEFAULT_MAX_VARIABLES,
    max_variables_per_shard: int = 5000,
    allow_external_qpu_benchmark: bool = False,
) -> dict[str, Any]:
    problem = compile_action_portfolio_problem(
        source_problem,
        workload_key=workload_key,
        tenant_id=tenant_id,
        time_budget_ms=time_budget_ms,
        cost_budget_minor_units=cost_budget_minor_units,
    )
    return build_optimization_fabric_plan(
        problem,
        runtime=runtime,
        exact_variable_limit=exact_variable_limit,
        max_variables_per_shard=max_variables_per_shard,
        allow_external_qpu_benchmark=allow_external_qpu_benchmark,
    )
