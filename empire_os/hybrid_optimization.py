"""Hybrid optimization planner for EmpireOS.

This layer decides *how to solve* an already-normalized optimization problem.
It never fabricates economics and never executes a commercial allocation.

Routing doctrine:
- small problems: exact classical reference first;
- larger unit-capacity problems: classical heuristic + QUBO/QAOA benchmark lane;
- general-capacity problems: classical heuristic + CQM/hybrid lane;
- no quantum/hybrid production claim without measured benchmark evidence.
"""
from __future__ import annotations

from typing import Any, Mapping

from empire_os.quantum_optimization import (
    MAX_EXACT_VARIABLES,
    build_cqm_export,
    build_qubo_export,
    solve_allocation_classical_exact,
)


SCHEMA_VERSION = "empire.hybrid_optimization.plan.v1"


def _status(packet: Mapping[str, Any]) -> str:
    return str(packet.get("status") or "").strip().upper()


def solve_allocation_classical_greedy(
    problem: Mapping[str, Any],
) -> dict[str, Any]:
    """Deterministic scalable baseline for larger allocation instances."""
    if _status(problem) != "AVAILABLE":
        return {
            "schema_version": "empire.hybrid_optimization.greedy.v1",
            "status": "UNAVAILABLE",
            "reason": "optimization_problem_unavailable",
            "execution_authority": "none",
        }

    capacities = {
        str(key): int(value)
        for key, value in dict(
            problem.get("buyer_capacities") or {}
        ).items()
    }
    rows = [
        row
        for row in (problem.get("variables") or [])
        if isinstance(row, Mapping)
    ]
    rows.sort(
        key=lambda row: (
            -float(row.get("expected_value_cents") or 0),
            str(row.get("prospect_id") or ""),
            str(row.get("buyer_id") or ""),
        )
    )

    used_buyers: dict[str, int] = {}
    used_prospects: set[str] = set()
    selected: list[dict[str, Any]] = []
    total = 0.0

    for row in rows:
        prospect_id = str(row.get("prospect_id") or "")
        buyer_id = str(row.get("buyer_id") or "")
        if not prospect_id or not buyer_id:
            continue
        if prospect_id in used_prospects:
            continue
        current = used_buyers.get(buyer_id, 0)
        if current >= capacities.get(buyer_id, 0):
            continue

        value = float(row.get("expected_value_cents") or 0)
        used_prospects.add(prospect_id)
        used_buyers[buyer_id] = current + 1
        total += value
        selected.append({
            "prospect_id": prospect_id,
            "buyer_id": buyer_id,
            "variable": row.get("variable"),
            "expected_value_cents": value,
            "evidence_refs": list(row.get("evidence_refs") or []),
        })

    return {
        "schema_version": "empire.hybrid_optimization.greedy.v1",
        "status": "AVAILABLE",
        "solver": "classical_greedy_baseline",
        "optimal_for_normalized_problem": False,
        "selected_assignments": selected,
        "selected_count": len(selected),
        "objective_value_cents": round(total, 4),
        "prediction_only": True,
        "actual_revenue": False,
        "allocation_execution": False,
        "execution_authority": "none",
    }


def build_hybrid_optimization_plan(
    problem: Mapping[str, Any],
    *,
    exact_variable_limit: int = MAX_EXACT_VARIABLES,
) -> dict[str, Any]:
    """Select classical and quantum/hybrid benchmark lanes."""
    if _status(problem) != "AVAILABLE":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "optimization_problem_unavailable",
            "execution_authority": "none",
        }

    variables = [
        row
        for row in (problem.get("variables") or [])
        if isinstance(row, Mapping)
    ]
    variable_count = len(variables)
    capacities = {
        str(key): int(value)
        for key, value in dict(
            problem.get("buyer_capacities") or {}
        ).items()
    }
    unit_capacity = all(
        value in (0, 1)
        for value in capacities.values()
    )

    greedy = solve_allocation_classical_greedy(problem)
    exact = (
        solve_allocation_classical_exact(
            problem,
            max_variables=exact_variable_limit,
        )
        if variable_count <= exact_variable_limit
        else {
            "status": "UNAVAILABLE",
            "reason": "exact_reference_variable_limit_exceeded",
            "variable_count": variable_count,
            "max_variables": exact_variable_limit,
        }
    )

    cqm = build_cqm_export(problem)
    qubo = build_qubo_export(problem)

    if _status(exact) == "AVAILABLE":
        primary_lane = "classical_exact"
        reference_quality = "OPTIMAL_REFERENCE"
    else:
        primary_lane = "classical_greedy"
        reference_quality = "HEURISTIC_REFERENCE"

    quantum_lane = (
        "QAOA_OR_BQM_BENCHMARK"
        if qubo.get("qaoa_ready") is True
        else "CQM_HYBRID_BENCHMARK"
        if _status(cqm) == "AVAILABLE"
        else "UNAVAILABLE"
    )

    benchmark_ready = (
        _status(greedy) == "AVAILABLE"
        and (
            _status(exact) == "AVAILABLE"
            or reference_quality == "HEURISTIC_REFERENCE"
        )
        and quantum_lane != "UNAVAILABLE"
    )

    production_promotion_ready = False

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE",
        "variable_count": variable_count,
        "buyer_count": len(capacities),
        "unit_capacity_problem": unit_capacity,
        "primary_classical_lane": primary_lane,
        "classical_reference_quality": reference_quality,
        "classical_exact": exact,
        "classical_greedy": greedy,
        "quantum_benchmark_lane": quantum_lane,
        "cqm_export": cqm,
        "qubo_export": qubo,
        "benchmark_ready": benchmark_ready,
        "benchmark_requirements": {
            "same_normalized_problem": True,
            "same_objective_semantics": True,
            "same_hard_constraints": True,
            "solution_feasibility_check": True,
            "objective_quality_comparison": True,
            "wall_clock_comparison": True,
            "compute_cost_comparison": True,
            "repeatability_review": True,
        },
        "production_promotion_ready": production_promotion_ready,
        "quantum_advantage_claimed": False,
        "external_quantum_solver_called": False,
        "allocation_execution": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def review_hybrid_benchmark(
    *,
    plan: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate one solver candidate without promoting it to production."""
    if _status(plan) != "AVAILABLE":
        return {
            "schema_version": "empire.hybrid_optimization.review.v1",
            "status": "UNAVAILABLE",
            "reason": "hybrid_plan_unavailable",
            "execution_authority": "none",
        }

    objective = candidate.get("objective_value_cents")
    feasible = candidate.get("constraints_satisfied")
    wall_clock_ms = candidate.get("wall_clock_ms")
    compute_cost = candidate.get("compute_cost_minor_units")

    missing = []
    if objective is None:
        missing.append("objective_value_cents")
    if feasible is None:
        missing.append("constraints_satisfied")
    if wall_clock_ms is None:
        missing.append("wall_clock_ms")
    if compute_cost is None:
        missing.append("compute_cost_minor_units")
    if missing:
        return {
            "schema_version": "empire.hybrid_optimization.review.v1",
            "status": "UNAVAILABLE",
            "missing_fields": missing,
            "reason": "benchmark_evidence_incomplete",
            "execution_authority": "none",
        }

    exact = plan.get("classical_exact")
    exact = exact if isinstance(exact, Mapping) else {}
    greedy = plan.get("classical_greedy")
    greedy = greedy if isinstance(greedy, Mapping) else {}

    reference = (
        exact
        if _status(exact) == "AVAILABLE"
        else greedy
    )
    reference_value = reference.get("objective_value_cents")
    if reference_value is None:
        return {
            "schema_version": "empire.hybrid_optimization.review.v1",
            "status": "UNAVAILABLE",
            "reason": "classical_reference_missing",
            "execution_authority": "none",
        }

    candidate_value = float(objective)
    reference_value = float(reference_value)
    objective_ratio = (
        candidate_value / reference_value
        if reference_value > 0
        else 1.0 if candidate_value == 0 else None
    )

    return {
        "schema_version": "empire.hybrid_optimization.review.v1",
        "status": "AVAILABLE",
        "solver": candidate.get("solver"),
        "constraints_satisfied": feasible is True,
        "candidate_objective_value_cents": candidate_value,
        "classical_reference_value_cents": reference_value,
        "objective_ratio": (
            round(objective_ratio, 8)
            if objective_ratio is not None
            else None
        ),
        "matches_or_beats_reference": (
            feasible is True
            and candidate_value >= reference_value
        ),
        "wall_clock_ms": float(wall_clock_ms),
        "compute_cost_minor_units": float(compute_cost),
        "production_promotion_ready": False,
        "quantum_advantage_claimed": False,
        "human_review_required": True,
        "execution_authority": "none",
    }
