"""Portfolio Next-Best-Action optimization for EmpireOS.

Consumes only evidence-backed incremental action value, applies explicit budget
and capacity constraints, provides deterministic classical references, and
emits provider-neutral CQM/QUBO benchmark representations.

This module never executes actions and never converts predicted value into
revenue truth.
"""
from __future__ import annotations

from itertools import combinations
from typing import Any, Mapping, Sequence

from empire_os.predictive_revenue_formula import next_best_action_value


SCHEMA_VERSION = "empire.action_portfolio_optimization.v1"
MAX_EXACT_VARIABLES = 24


def _status(value: Mapping[str, Any]) -> str:
    return str(value.get("status") or "").strip().upper()


def _nonnegative(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if number < 0:
        raise ValueError(f"{name} must be nonnegative")
    return number


def build_portfolio_optimization_problem(
    *,
    actions: Sequence[Mapping[str, Any]],
    budget_cents: Any,
    capacity_constraints: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        budget = _nonnegative(budget_cents, "budget_cents")
    except ValueError:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "budget_unknown_or_invalid",
            "unknown_is_zero": False,
            "execution_authority": "none",
        }

    capacities: dict[str, int] = {}
    for key, value in dict(capacity_constraints or {}).items():
        name = str(key or "").strip()
        if not name:
            continue
        try:
            number = int(value)
        except (TypeError, ValueError):
            return {
                "schema_version": SCHEMA_VERSION,
                "status": "UNAVAILABLE",
                "reason": "capacity_unknown_or_invalid",
                "unknown_capacity_group": name,
                "unknown_is_zero": False,
                "execution_authority": "none",
            }
        if number < 0:
            return {
                "schema_version": SCHEMA_VERSION,
                "status": "UNAVAILABLE",
                "reason": "capacity_unknown_or_invalid",
                "unknown_capacity_group": name,
                "unknown_is_zero": False,
                "execution_authority": "none",
            }
        capacities[name] = number

    variables: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    seen: set[str] = set()

    for raw in actions:
        action_key = str(raw.get("action_key") or "").strip()
        refs = tuple(dict.fromkeys(
            str(ref).strip()
            for ref in (raw.get("evidence_refs") or ())
            if str(ref).strip()
        ))
        value = raw.get("expected_incremental_value_cents")
        cost = raw.get("action_cost_cents")
        group = str(raw.get("capacity_group") or "").strip() or None

        missing = []
        if not action_key:
            missing.append("action_key")
        if value is None:
            missing.append("expected_incremental_value_cents")
        if cost is None:
            missing.append("action_cost_cents")
        if not refs:
            missing.append("evidence_refs")
        if group is not None and group not in capacities:
            missing.append("capacity_constraint")
        if missing:
            blocked.append({
                "action_key": action_key or None,
                "missing_fields": missing,
                "reason": "unknown_action_economics_preserved",
            })
            continue

        if action_key in seen:
            blocked.append({
                "action_key": action_key,
                "reason": "duplicate_action_key",
            })
            continue
        seen.add(action_key)

        try:
            expected_value = _nonnegative(
                value,
                "expected_incremental_value_cents",
            )
            action_cost = _nonnegative(cost, "action_cost_cents")
        except ValueError:
            blocked.append({
                "action_key": action_key,
                "reason": "invalid_action_economics",
            })
            continue

        if action_cost > budget:
            blocked.append({
                "action_key": action_key,
                "reason": "action_exceeds_budget",
            })
            continue

        variables.append({
            "variable": f"x::{action_key}",
            "action_key": action_key,
            "expected_incremental_value_cents": expected_value,
            "action_cost_cents": action_cost,
            "capacity_group": group,
            "evidence_refs": refs,
        })

    constraints: list[dict[str, Any]] = [{
        "name": "total_budget",
        "coefficients": {
            row["variable"]: row["action_cost_cents"]
            for row in variables
        },
        "sense": "<=",
        "rhs": budget,
        "constraint_type": "hard",
    }]
    for group, capacity in sorted(capacities.items()):
        coefficients = {
            row["variable"]: 1
            for row in variables
            if row["capacity_group"] == group
        }
        if coefficients:
            constraints.append({
                "name": f"capacity_group::{group}",
                "coefficients": coefficients,
                "sense": "<=",
                "rhs": capacity,
                "constraint_type": "hard",
            })

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE" if variables else "UNAVAILABLE",
        "reason": None if variables else "no_affordable_actions",
        "variables": variables,
        "budget_cents": budget,
        "capacity_constraints": capacities,
        "constraints": constraints,
        "blocked_actions": blocked,
        "unknown_is_zero": False,
        "recommendation_only": True,
        "portfolio_execution": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def _feasible(
    selected: Sequence[Mapping[str, Any]],
    *,
    budget: float,
    capacities: Mapping[str, int],
) -> bool:
    if sum(float(row["action_cost_cents"]) for row in selected) > budget:
        return False
    used: dict[str, int] = {}
    for row in selected:
        group = row.get("capacity_group")
        if not group:
            continue
        used[str(group)] = used.get(str(group), 0) + 1
    return all(used.get(group, 0) <= cap for group, cap in capacities.items())


def solve_portfolio_classical_exact(
    problem: Mapping[str, Any],
    *,
    max_variables: int = MAX_EXACT_VARIABLES,
) -> dict[str, Any]:
    if _status(problem) != "AVAILABLE":
        return {
            "status": "UNAVAILABLE",
            "reason": "optimization_problem_unavailable",
            "execution_authority": "none",
        }
    rows = list(problem.get("variables") or [])
    if len(rows) > max_variables:
        return {
            "status": "UNAVAILABLE",
            "reason": "exact_reference_variable_limit_exceeded",
            "variable_count": len(rows),
            "max_variables": max_variables,
            "execution_authority": "none",
        }

    best: list[Mapping[str, Any]] = []
    best_value = -1.0
    for size in range(len(rows) + 1):
        for combo in combinations(rows, size):
            if not _feasible(
                combo,
                budget=float(problem["budget_cents"]),
                capacities=dict(problem.get("capacity_constraints") or {}),
            ):
                continue
            value = sum(
                float(row["expected_incremental_value_cents"])
                for row in combo
            )
            signature = tuple(sorted(str(row["action_key"]) for row in combo))
            best_signature = tuple(sorted(str(row["action_key"]) for row in best))
            if value > best_value or (
                value == best_value and signature < best_signature
            ):
                best_value = value
                best = list(combo)

    total_cost = sum(float(row["action_cost_cents"]) for row in best)
    return {
        "schema_version": "empire.action_portfolio.classical_exact.v1",
        "status": "AVAILABLE",
        "solver": "classical_exact",
        "selected_actions": [dict(row) for row in best],
        "selected_count": len(best),
        "objective_value_cents": round(max(best_value, 0.0), 4),
        "total_cost_cents": round(total_cost, 4),
        "optimal_for_normalized_problem": True,
        "portfolio_execution": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def solve_portfolio_classical_greedy(
    problem: Mapping[str, Any],
) -> dict[str, Any]:
    if _status(problem) != "AVAILABLE":
        return {
            "status": "UNAVAILABLE",
            "reason": "optimization_problem_unavailable",
            "execution_authority": "none",
        }
    rows = list(problem.get("variables") or [])
    rows.sort(key=lambda row: (
        -(
            float(row["expected_incremental_value_cents"])
            / max(float(row["action_cost_cents"]), 1.0)
        ),
        str(row["action_key"]),
    ))

    selected: list[Mapping[str, Any]] = []
    for row in rows:
        candidate = [*selected, row]
        if _feasible(
            candidate,
            budget=float(problem["budget_cents"]),
            capacities=dict(problem.get("capacity_constraints") or {}),
        ):
            selected.append(row)

    return {
        "schema_version": "empire.action_portfolio.classical_greedy.v1",
        "status": "AVAILABLE",
        "solver": "classical_greedy",
        "selected_actions": [dict(row) for row in selected],
        "selected_count": len(selected),
        "objective_value_cents": round(sum(
            float(row["expected_incremental_value_cents"])
            for row in selected
        ), 4),
        "total_cost_cents": round(sum(
            float(row["action_cost_cents"])
            for row in selected
        ), 4),
        "optimal_for_normalized_problem": False,
        "portfolio_execution": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def build_cqm_export(problem: Mapping[str, Any]) -> dict[str, Any]:
    if _status(problem) != "AVAILABLE":
        return {
            "status": "UNAVAILABLE",
            "reason": "optimization_problem_unavailable",
            "execution_authority": "none",
        }
    return {
        "schema_version": "empire.action_portfolio.cqm.v1",
        "status": "AVAILABLE",
        "model_type": "CONSTRAINED_QUADRATIC_MODEL",
        "variable_type": "BINARY",
        "objective_sense": "MAXIMIZE",
        "linear": {
            row["variable"]: float(row["expected_incremental_value_cents"])
            for row in problem.get("variables") or []
        },
        "quadratic": {},
        "constraints": list(problem.get("constraints") or []),
        "external_solver_called": False,
        "execution_authority": "none",
    }


def build_qubo_export(problem: Mapping[str, Any]) -> dict[str, Any]:
    if _status(problem) != "AVAILABLE":
        return {
            "status": "UNAVAILABLE",
            "reason": "optimization_problem_unavailable",
            "qaoa_ready": False,
            "execution_authority": "none",
        }

    rows = list(problem.get("variables") or [])
    scale = max(
        [float(row["action_cost_cents"]) for row in rows] + [1.0]
    )
    budget_penalty = max(
        [float(row["expected_incremental_value_cents"]) for row in rows]
        + [1.0]
    ) * 2.0
    capacity_penalty = budget_penalty

    linear = {
        row["variable"]: -float(row["expected_incremental_value_cents"])
        for row in rows
    }
    quadratic: dict[str, float] = {}

    # Pairwise penalties provide a provider-neutral benchmark representation.
    for left, right in combinations(rows, 2):
        key = f"{left['variable']}|{right['variable']}"
        penalty = (
            budget_penalty
            * float(left["action_cost_cents"])
            * float(right["action_cost_cents"])
            / (scale * scale)
        )
        if (
            left.get("capacity_group")
            and left.get("capacity_group") == right.get("capacity_group")
            and int(
                dict(problem.get("capacity_constraints") or {}).get(
                    str(left["capacity_group"]),
                    999999,
                )
            ) <= 1
        ):
            penalty += capacity_penalty
        quadratic[key] = round(penalty, 8)

    return {
        "schema_version": "empire.action_portfolio.qubo.v1",
        "status": "AVAILABLE",
        "model_type": "QUBO",
        "objective_sense": "MINIMIZE",
        "linear": linear,
        "quadratic": quadratic,
        "normalization_scale_cents": scale,
        "budget_penalty_multiplier": budget_penalty,
        "capacity_penalty_multiplier": capacity_penalty,
        "qaoa_ready": True,
        "external_solver_called": False,
        "execution_authority": "none",
    }


def build_portfolio_optimization_plan(
    problem: Mapping[str, Any],
    *,
    exact_variable_limit: int = MAX_EXACT_VARIABLES,
) -> dict[str, Any]:
    if _status(problem) != "AVAILABLE":
        return {
            "status": "UNAVAILABLE",
            "reason": "optimization_problem_unavailable",
            "execution_authority": "none",
        }

    exact = solve_portfolio_classical_exact(
        problem,
        max_variables=exact_variable_limit,
    )
    greedy = solve_portfolio_classical_greedy(problem)
    cqm = build_cqm_export(problem)
    qubo = build_qubo_export(problem)

    if _status(exact) == "AVAILABLE":
        primary = "classical_exact"
        quality = "OPTIMAL_REFERENCE"
    else:
        primary = "classical_greedy"
        quality = "HEURISTIC_REFERENCE"

    return {
        "schema_version": "empire.action_portfolio.plan.v1",
        "status": "AVAILABLE",
        "primary_classical_lane": primary,
        "classical_reference_quality": quality,
        "classical_exact": exact,
        "classical_greedy": greedy,
        "cqm_export": cqm,
        "qubo_export": qubo,
        "quantum_benchmark_lane": "QAOA_OR_BQM_BENCHMARK",
        "benchmark_ready": True,
        "production_promotion_ready": False,
        "quantum_advantage_claimed": False,
        "portfolio_execution": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def optimize_action_portfolio(
    *,
    nba_actions: Sequence[Mapping[str, Any]],
    budget_cents: Any,
    capacity_constraints: Mapping[str, Any] | None = None,
    exact_variable_limit: int = MAX_EXACT_VARIABLES,
) -> dict[str, Any]:
    scored = next_best_action_value(nba_actions)
    raw_by_key = {
        str(row.get("action_key") or ""): row
        for row in nba_actions
        if str(row.get("action_key") or "")
    }

    normalized: list[dict[str, Any]] = []
    for row in scored.get("actions") or []:
        raw = raw_by_key.get(str(row.get("action_key") or ""), {})
        normalized.append({
            "action_key": row["action_key"],
            "expected_incremental_value_cents": row[
                "expected_incremental_value_cents"
            ],
            "action_cost_cents": row["action_cost_cents"],
            "capacity_group": raw.get("capacity_group"),
            "evidence_refs": raw.get("evidence_refs") or (),
        })

    problem = build_portfolio_optimization_problem(
        actions=normalized,
        budget_cents=budget_cents,
        capacity_constraints=capacity_constraints,
    )
    plan = build_portfolio_optimization_plan(
        problem,
        exact_variable_limit=exact_variable_limit,
    )
    plan["nba_context"] = {
        "total_nba_actions": len(normalized),
        "unavailable_nba_actions": int(
            scored.get("unavailable_action_count") or 0
        ),
        "nba_recommendation_only": True,
    }
    plan["problem"] = problem
    return plan


def review_portfolio_benchmark(
    *,
    plan: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    if _status(plan) != "AVAILABLE":
        return {
            "status": "UNAVAILABLE",
            "reason": "portfolio_plan_unavailable",
            "execution_authority": "none",
        }

    required = (
        "objective_value_cents",
        "constraints_satisfied",
        "wall_clock_ms",
        "compute_cost_minor_units",
    )
    missing = [
        field for field in required
        if candidate.get(field) is None
    ]
    if missing:
        return {
            "status": "UNAVAILABLE",
            "reason": "benchmark_evidence_incomplete",
            "missing_fields": missing,
            "execution_authority": "none",
        }

    exact = plan.get("classical_exact") or {}
    greedy = plan.get("classical_greedy") or {}
    reference = exact if _status(exact) == "AVAILABLE" else greedy
    reference_value = float(reference.get("objective_value_cents") or 0)
    candidate_value = float(candidate["objective_value_cents"])

    return {
        "schema_version": "empire.action_portfolio.review.v1",
        "status": "AVAILABLE",
        "solver": candidate.get("solver"),
        "constraints_satisfied": candidate["constraints_satisfied"] is True,
        "candidate_objective_value_cents": candidate_value,
        "classical_reference_value_cents": reference_value,
        "matches_or_beats_reference": (
            candidate["constraints_satisfied"] is True
            and candidate_value >= reference_value
        ),
        "wall_clock_ms": float(candidate["wall_clock_ms"]),
        "compute_cost_minor_units": float(
            candidate["compute_cost_minor_units"]
        ),
        "production_promotion_ready": False,
        "quantum_advantage_claimed": False,
        "human_review_required": True,
        "portfolio_execution": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }
