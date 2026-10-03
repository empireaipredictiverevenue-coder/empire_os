"""Empire-owned Large-Neighbourhood Search for binary linear Optimization IR.

LNS starts from an Empire Branch-and-Bound incumbent, repeatedly frees a small
subset of variables, freezes the rest, and lets the same Empire-owned exact
engine optimize that neighbourhood. It is intended for larger portfolio and
allocation workloads where full search may exceed the requested latency budget.
"""
from __future__ import annotations

import random
import time
from typing import Any, Mapping

from empire_os.optimization_problem_factory import (
    build_problem_ir,
    validate_problem_integrity,
)
from empire_os.solver_adapters.empire_branch_bound import (
    solve_empire_branch_bound,
)


SCHEMA_VERSION = "empire.solver.empire_large_neighborhood.v1"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _better(
    candidate: float,
    incumbent: float,
    *,
    sense: str,
) -> bool:
    if sense == "MAXIMIZE":
        return candidate > incumbent + 1e-12
    return candidate < incumbent - 1e-12


def solve_empire_large_neighborhood(
    problem: Mapping[str, Any],
    *,
    neighborhood_size: int = 12,
    max_rounds: int = 40,
    seed: int = 1729,
    max_wall_clock_ms: Any = None,
    seed_node_limit: int = 250_000,
    neighborhood_node_limit: int = 200_000,
) -> dict[str, Any]:
    """Run bounded Empire-owned LNS over a normalized binary linear problem."""
    integrity = validate_problem_integrity(problem)
    if str(integrity.get("status") or "").upper() != "AVAILABLE":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "optimization_problem_integrity_failed",
            "integrity": integrity,
            "execution_authority": "none",
        }
    if _text(problem.get("variable_type")).upper() != "BINARY":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "binary_variables_only",
            "execution_authority": "none",
        }
    objective = dict(problem.get("objective") or {})
    if dict(objective.get("quadratic") or {}):
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "quadratic_objective_not_supported_v1",
            "execution_authority": "none",
        }
    sense = _text(objective.get("sense")).upper()
    if sense not in {"MAXIMIZE", "MINIMIZE"}:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "unsupported_objective_sense",
            "execution_authority": "none",
        }
    if neighborhood_size <= 0 or max_rounds <= 0:
        raise ValueError("neighborhood_size and max_rounds must be positive")
    if seed_node_limit <= 0 or neighborhood_node_limit <= 0:
        raise ValueError("node limits must be positive")

    raw_budget = (
        max_wall_clock_ms
        if max_wall_clock_ms is not None
        else problem.get("time_budget_ms")
    )
    if raw_budget is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "time_budget_required",
            "execution_authority": "none",
        }
    try:
        total_budget_ms = float(raw_budget)
    except (TypeError, ValueError):
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "time_budget_invalid",
            "execution_authority": "none",
        }
    if total_budget_ms <= 0:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "time_budget_must_be_positive",
            "execution_authority": "none",
        }

    variables = [
        _text(row.get("variable"))
        for row in (problem.get("variables") or ())
        if isinstance(row, Mapping) and _text(row.get("variable"))
    ]
    variables = sorted(set(variables))
    if not variables:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "no_variables",
            "execution_authority": "none",
        }

    started = time.perf_counter()
    deadline = started + total_budget_ms / 1000.0
    seed_budget_ms = max(
        1.0,
        min(total_budget_ms * 0.35, total_budget_ms),
    )
    seed_result = solve_empire_branch_bound(
        problem,
        max_wall_clock_ms=seed_budget_ms,
        max_nodes=seed_node_limit,
    )
    if str(seed_result.get("status") or "").upper() != "AVAILABLE":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "no_feasible_seed_solution",
            "seed_result": seed_result,
            "problem_fingerprint": problem.get("problem_fingerprint"),
            "external_solver_called": False,
            "execution_authority": "none",
        }

    incumbent_assignment = dict(seed_result.get("assignment") or {})
    incumbent_value = float(seed_result.get("objective_value"))
    if seed_result.get("optimal_for_normalized_problem") is True:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "AVAILABLE",
            "solve_status": "SEED_PROVED_OPTIMAL",
            "problem_fingerprint": problem.get("problem_fingerprint"),
            "solver": "empire_large_neighborhood",
            "solver_family": "empire_large_neighborhood_search",
            "hardware_class": "cpu",
            "assignment": incumbent_assignment,
            "selected_variables": list(
                seed_result.get("selected_variables") or []
            ),
            "selected_count": seed_result.get("selected_count"),
            "objective_value": incumbent_value,
            "constraints_satisfied": (
                seed_result.get("constraints_satisfied") is True
            ),
            "seed_solver": "empire_branch_bound",
            "seed_proved_optimal": True,
            "rounds_completed": 0,
            "improvement_count": 0,
            "wall_clock_ms": round(
                (time.perf_counter() - started) * 1000.0,
                6,
            ),
            "compute_cost_minor_units": None,
            "compute_cost_known": False,
            "external_solver_called": False,
            "third_party_runtime_dependency": False,
            "production_promotion_ready": False,
            "execution_authority": "none",
        }

    rng = random.Random(int(seed))
    improvements = 0
    rounds_completed = 0
    timed_out = False
    variable_rows = [
        dict(row)
        for row in (problem.get("variables") or ())
        if isinstance(row, Mapping)
    ]

    for round_index in range(max_rounds):
        remaining_ms = (deadline - time.perf_counter()) * 1000.0
        if remaining_ms <= 1.0:
            timed_out = True
            break

        k = min(neighborhood_size, len(variables))
        if round_index == 0:
            ranked = sorted(
                variables,
                key=lambda name: (
                    -abs(
                        float(
                            dict(objective.get("linear") or {}).get(
                                name, 0.0
                            )
                        )
                    ),
                    name,
                ),
            )
            free = set(ranked[:k])
        else:
            free = set(rng.sample(variables, k))

        fixed_constraints = []
        for variable in variables:
            if variable in free:
                continue
            fixed_constraints.append({
                "name": f"lns_fix::{round_index}::{variable}",
                "coefficients": {variable: 1},
                "sense": "==",
                "rhs": int(incumbent_assignment.get(variable, 0)),
                "constraint_type": "lns_fixed_variable",
            })

        subproblem = build_problem_ir(
            workload_key=(
                f"{problem.get('workload_key')}::lns::{round_index}"
            ),
            workload_type=str(problem.get("workload_type") or ""),
            source_schema_version=str(
                problem.get("source_schema_version") or SCHEMA_VERSION
            ),
            variable_type="BINARY",
            variables=variable_rows,
            objective=objective,
            constraints=[
                *[
                    dict(row)
                    for row in (problem.get("constraints") or ())
                    if isinstance(row, Mapping)
                ],
                *fixed_constraints,
            ],
            evidence_refs=problem.get("evidence_refs") or (),
            tenant_id=problem.get("tenant_id"),
            time_budget_ms=max(1.0, remaining_ms),
            cost_budget_minor_units=problem.get(
                "cost_budget_minor_units"
            ),
            representations=problem.get("representations") or (),
            metadata={
                **dict(problem.get("metadata") or {}),
                "lns_parent_problem_fingerprint": problem.get(
                    "problem_fingerprint"
                ),
                "lns_round": round_index,
                "lns_free_variable_count": len(free),
            },
        )
        result = solve_empire_branch_bound(
            subproblem,
            max_wall_clock_ms=max(1.0, remaining_ms),
            max_nodes=neighborhood_node_limit,
        )
        rounds_completed += 1
        if str(result.get("status") or "").upper() != "AVAILABLE":
            continue
        candidate_value = float(result.get("objective_value"))
        if _better(candidate_value, incumbent_value, sense=sense):
            incumbent_value = candidate_value
            incumbent_assignment = dict(result.get("assignment") or {})
            improvements += 1

    wall_clock_ms = (time.perf_counter() - started) * 1000.0
    selected = sorted(
        variable
        for variable, value in incumbent_assignment.items()
        if int(value) == 1
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE",
        "solve_status": (
            "TIME_LIMIT_FEASIBLE" if timed_out else "LNS_FEASIBLE"
        ),
        "problem_fingerprint": problem.get("problem_fingerprint"),
        "solver": "empire_large_neighborhood",
        "solver_family": "empire_large_neighborhood_search",
        "hardware_class": "cpu",
        "assignment": incumbent_assignment,
        "selected_variables": selected,
        "selected_count": len(selected),
        "objective_value": round(incumbent_value, 8),
        "constraints_satisfied": True,
        "seed_solver": "empire_branch_bound",
        "seed_proved_optimal": False,
        "neighborhood_size": min(neighborhood_size, len(variables)),
        "rounds_requested": max_rounds,
        "rounds_completed": rounds_completed,
        "improvement_count": improvements,
        "seed": int(seed),
        "timed_out": timed_out,
        "wall_clock_ms": round(wall_clock_ms, 6),
        "compute_cost_minor_units": None,
        "compute_cost_known": False,
        "external_solver_called": False,
        "third_party_runtime_dependency": False,
        "prediction_only": True,
        "actual_revenue": False,
        "production_promotion_ready": False,
        "execution_authority": "none",
    }
