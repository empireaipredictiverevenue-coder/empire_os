"""Evidence-only solver policy over canonical Solver Performance Memory.

Solver Performance Memory is the single owner of benchmark aggregation.
This module applies a bounded policy to that memory for one current fabric plan.
It never mutates production routing, promotes a solver, or claims quantum
advantage.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from empire_os.solver_performance_memory import (
    build_solver_performance_memory,
    workload_signature,
)


SCHEMA_VERSION = "empire.optimization.solver-policy.v1"

EMPIRE_POLICY_SOLVERS = frozenset({
    "classical_exact_binary_ir",
    "classical_exact_reference",
    "classical_greedy_reference",
    "empire_branch_bound",
    "empire_annealing",
    "empire_parallel_tempering",
    "empire_qaoa_simulator",
})


def _empire_solver(solver: Any) -> bool:
    return str(solver or "").strip() in EMPIRE_POLICY_SOLVERS


def _text(value: Any) -> str:
    return str(value or "").strip()


def _status(packet: Mapping[str, Any]) -> str:
    return _text(packet.get("status")).upper()


def build_solver_policy_profile(
    arenas: Sequence[Mapping[str, Any]],
    *,
    minimum_observations: int = 3,
    allow_external_candidates: bool = False,
) -> dict[str, Any]:
    """Build one policy profile from canonical solver-performance memory."""
    if allow_external_candidates:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "external_solver_policy_not_supported",
            "automatic_production_routing_changed": False,
            "production_promotion_ready": False,
            "quantum_advantage_claimed": False,
            "execution_authority": "none",
        }

    usable_arena_count = sum(
        1
        for row in arenas
        if isinstance(row, Mapping) and _status(row) == "AVAILABLE"
    )
    if usable_arena_count < minimum_observations:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "insufficient_benchmark_arenas",
            "observed_arena_count": usable_arena_count,
            "minimum_observations": minimum_observations,
            "automatic_production_routing_changed": False,
            "production_promotion_ready": False,
            "quantum_advantage_claimed": False,
            "execution_authority": "none",
        }

    memory = build_solver_performance_memory(
        arenas,
        minimum_observations=minimum_observations,
    )
    if _status(memory) != "AVAILABLE":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": (
                "insufficient_benchmark_arenas"
                if not arenas or len(arenas) < minimum_observations
                else "solver_performance_memory_unavailable"
            ),
            "observed_arena_count": len(arenas),
            "minimum_observations": minimum_observations,
            "memory": memory,
            "automatic_production_routing_changed": False,
            "production_promotion_ready": False,
            "quantum_advantage_claimed": False,
            "execution_authority": "none",
        }

    profiles = dict(memory.get("profiles") or {})
    if len(profiles) != 1:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "mixed_workload_shape",
            "profile_count": len(profiles),
            "profile_signatures": sorted(profiles),
            "memory": memory,
            "automatic_production_routing_changed": False,
            "production_promotion_ready": False,
            "quantum_advantage_claimed": False,
            "execution_authority": "none",
        }

    signature, profile = next(iter(profiles.items()))
    if not isinstance(profile, Mapping):
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "solver_performance_profile_invalid",
            "execution_authority": "none",
        }

    usable = [
        row
        for row in arenas
        if isinstance(row, Mapping) and _status(row) == "AVAILABLE"
    ]
    baseline_solvers = {
        _text(row.get("baseline_solver"))
        for row in usable
        if _text(row.get("baseline_solver"))
    }
    if len(baseline_solvers) != 1:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "inconsistent_baseline_solver",
            "baseline_solvers": sorted(baseline_solvers),
            "memory": memory,
            "automatic_production_routing_changed": False,
            "production_promotion_ready": False,
            "quantum_advantage_claimed": False,
            "execution_authority": "none",
        }
    baseline_solver = next(iter(baseline_solvers))

    raw_solver_profiles = dict(profile.get("solver_profiles") or {})
    solver_profiles = {
        solver: dict(row)
        for solver, row in raw_solver_profiles.items()
        if _empire_solver(solver) and isinstance(row, Mapping)
    }
    excluded_market_reference_solvers = sorted(
        solver
        for solver in raw_solver_profiles
        if not _empire_solver(solver)
    )
    candidates = [
        dict(row)
        for solver, row in solver_profiles.items()
        if solver != baseline_solver
        and row.get("recommendation_eligible") is True
    ]
    candidates.sort(
        key=lambda row: (
            float(row.get("mean_wall_clock_ms") or float("inf")),
            0
            if row.get("mean_compute_cost_minor_units") is not None
            else 1,
            float(row.get("mean_compute_cost_minor_units") or 0.0),
            str(row.get("solver") or ""),
        )
    )
    recommended = candidates[0]["solver"] if candidates else None

    workload_type = _text(usable[0].get("workload_type")) if usable else None
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE",
        "workload_type": workload_type,
        "workload_signature": signature,
        "arena_count": len(usable),
        "minimum_observations": minimum_observations,
        "baseline_solver": baseline_solver,
        "solver_profiles": solver_profiles,
        "excluded_market_reference_solvers": excluded_market_reference_solvers,
        "market_reference_solvers_can_influence_policy": False,
        "recommended_nonbaseline_solver": recommended,
        "recommendation_basis": (
            "canonical_memory_quality_gate_then_lowest_observed_mean_latency"
            if recommended
            else "no_nonbaseline_solver_meets_canonical_memory_gate"
        ),
        "memory_schema_version": memory.get("schema_version"),
        "memory_profile_count": memory.get("profile_count"),
        "external_candidates_allowed": False,
        "recommendation_only": True,
        "automatic_production_routing_changed": False,
        "production_promotion_ready": False,
        "quantum_advantage_claimed": False,
        "human_review_required": True,
        "execution_authority": "none",
    }


def recommend_solver_for_plan(
    fabric_plan: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Return evidence-only solver advice for one immutable fabric plan."""
    if _status(fabric_plan) != "AVAILABLE":
        return {
            "schema_version": "empire.optimization.solver-policy-advice.v1",
            "status": "UNAVAILABLE",
            "reason": "fabric_plan_unavailable",
            "execution_authority": "none",
        }
    if _status(policy) != "AVAILABLE":
        return {
            "schema_version": "empire.optimization.solver-policy-advice.v1",
            "status": "UNAVAILABLE",
            "reason": "solver_policy_unavailable",
            "execution_authority": "none",
        }

    try:
        current_signature = workload_signature(fabric_plan)
    except ValueError:
        return {
            "schema_version": "empire.optimization.solver-policy-advice.v1",
            "status": "UNAVAILABLE",
            "reason": "fabric_plan_shape_unavailable",
            "execution_authority": "none",
        }
    if current_signature != _text(policy.get("workload_signature")):
        return {
            "schema_version": "empire.optimization.solver-policy-advice.v1",
            "status": "UNAVAILABLE",
            "reason": "workload_shape_mismatch",
            "current_signature": current_signature,
            "policy_signature": policy.get("workload_signature"),
            "execution_authority": "none",
        }

    recommended = _text(policy.get("recommended_nonbaseline_solver"))
    if recommended and not _empire_solver(recommended):
        return {
            "schema_version": "empire.optimization.solver-policy-advice.v1",
            "status": "UNAVAILABLE",
            "reason": "non_empire_solver_recommendation_rejected",
            "recommended_solver": recommended,
            "production_routing_changed": False,
            "execution_authority": "none",
        }
    if not recommended:
        return {
            "schema_version": "empire.optimization.solver-policy-advice.v1",
            "status": "AVAILABLE",
            "workload_signature": current_signature,
            "recommended_solver": None,
            "reason": "no_qualified_nonbaseline_solver",
            "recommendation_only": True,
            "automatic_production_routing_changed": False,
            "production_promotion_ready": False,
            "execution_authority": "none",
        }

    route = fabric_plan.get("solver_route")
    route = route if isinstance(route, Mapping) else {}
    primary = _text(route.get("primary_solver"))
    if recommended == primary:
        return {
            "schema_version": "empire.optimization.solver-policy-advice.v1",
            "status": "AVAILABLE",
            "workload_signature": current_signature,
            "recommended_solver": recommended,
            "reason": "recommended_solver_is_current_primary",
            "recommendation_only": True,
            "automatic_production_routing_changed": False,
            "production_promotion_ready": False,
            "quantum_advantage_claimed": False,
            "human_review_required": True,
            "execution_authority": "none",
        }

    lane = next(
        (
            row
            for row in (route.get("benchmark_lanes") or ())
            if isinstance(row, Mapping)
            and _text(row.get("solver")) == recommended
        ),
        None,
    )
    if lane is None:
        return {
            "schema_version": "empire.optimization.solver-policy-advice.v1",
            "status": "HELD",
            "workload_signature": current_signature,
            "recommended_solver": recommended,
            "reason": "recommended_solver_not_present_in_current_route",
            "recommendation_only": True,
            "automatic_production_routing_changed": False,
            "production_promotion_ready": False,
            "execution_authority": "none",
        }
    if lane.get("runnable") is not True:
        return {
            "schema_version": "empire.optimization.solver-policy-advice.v1",
            "status": "HELD",
            "workload_signature": current_signature,
            "recommended_solver": recommended,
            "reason": "recommended_solver_not_currently_runnable",
            "current_blockers": list(lane.get("blockers") or ()),
            "recommendation_only": True,
            "automatic_production_routing_changed": False,
            "production_promotion_ready": False,
            "execution_authority": "none",
        }

    return {
        "schema_version": "empire.optimization.solver-policy-advice.v1",
        "status": "AVAILABLE",
        "workload_signature": current_signature,
        "recommended_solver": recommended,
        "reason": "canonical_performance_memory_gate_passed",
        "current_lane": dict(lane),
        "recommendation_only": True,
        "automatic_production_routing_changed": False,
        "production_promotion_ready": False,
        "quantum_advantage_claimed": False,
        "human_review_required": True,
        "execution_authority": "none",
    }
