"""Empire-owned branch-and-bound solver for binary linear optimization IR.

No external solver SDK is used. The implementation is deliberately bounded,
deterministic and evidence-preserving. V1 supports binary linear objectives and
linear hard constraints.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import inf
import time
from typing import Any, Mapping

from empire_os.optimization_problem_factory import validate_problem_integrity


SCHEMA_VERSION = "empire.solver.empire_branch_bound.v1"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if result != result or result in (inf, -inf):
        raise ValueError(f"{name} must be finite")
    return result


@dataclass(frozen=True)
class _Constraint:
    name: str
    coefficients: dict[str, float]
    sense: str
    rhs: float


def _constraints(problem: Mapping[str, Any]) -> list[_Constraint]:
    rows: list[_Constraint] = []
    for index, raw in enumerate(problem.get("constraints") or ()):
        if not isinstance(raw, Mapping):
            continue
        name = _text(raw.get("name")) or f"constraint::{index}"
        sense = _text(raw.get("sense"))
        if sense == "=":
            sense = "=="
        if sense not in {"<=", ">=", "=="}:
            raise ValueError(f"unsupported constraint sense:{name}:{sense}")
        rows.append(
            _Constraint(
                name=name,
                coefficients={
                    str(variable): _number(
                        coefficient,
                        f"constraint:{name}:{variable}",
                    )
                    for variable, coefficient in dict(
                        raw.get("coefficients") or {}
                    ).items()
                },
                sense=sense,
                rhs=_number(raw.get("rhs"), f"constraint:{name}:rhs"),
            )
        )
    return rows


def _partial_constraint_possible(
    constraint: _Constraint,
    assignment: Mapping[str, int],
    remaining: set[str],
    *,
    tolerance: float = 1e-9,
) -> bool:
    current = 0.0
    minimum_extra = 0.0
    maximum_extra = 0.0
    for variable, coefficient in constraint.coefficients.items():
        if variable in assignment:
            current += coefficient * int(assignment[variable])
        elif variable in remaining:
            minimum_extra += min(0.0, coefficient)
            maximum_extra += max(0.0, coefficient)

    minimum_possible = current + minimum_extra
    maximum_possible = current + maximum_extra
    if constraint.sense == "<=":
        return minimum_possible <= constraint.rhs + tolerance
    if constraint.sense == ">=":
        return maximum_possible >= constraint.rhs - tolerance
    return (
        minimum_possible <= constraint.rhs + tolerance
        and maximum_possible >= constraint.rhs - tolerance
    )


def _fully_feasible(
    constraints: list[_Constraint],
    assignment: Mapping[str, int],
    *,
    tolerance: float = 1e-9,
) -> tuple[bool, list[dict[str, Any]]]:
    violations: list[dict[str, Any]] = []
    for row in constraints:
        lhs = sum(
            coefficient * int(assignment.get(variable, 0))
            for variable, coefficient in row.coefficients.items()
        )
        ok = (
            lhs <= row.rhs + tolerance
            if row.sense == "<="
            else lhs >= row.rhs - tolerance
            if row.sense == ">="
            else abs(lhs - row.rhs) <= tolerance
        )
        if not ok:
            violations.append({
                "constraint": row.name,
                "lhs": lhs,
                "sense": row.sense,
                "rhs": row.rhs,
            })
    return not violations, violations


def _objective_value(
    coefficients: Mapping[str, float],
    assignment: Mapping[str, int],
) -> float:
    return sum(
        coefficient * int(assignment.get(variable, 0))
        for variable, coefficient in coefficients.items()
    )


def _objective_bound(
    *,
    current_value: float,
    remaining: set[str],
    coefficients: Mapping[str, float],
    sense: str,
) -> float:
    if sense == "MAXIMIZE":
        return current_value + sum(
            max(0.0, coefficients.get(variable, 0.0))
            for variable in remaining
        )
    return current_value + sum(
        min(0.0, coefficients.get(variable, 0.0))
        for variable in remaining
    )


def _better(
    candidate_value: float,
    incumbent_value: float | None,
    *,
    sense: str,
) -> bool:
    if incumbent_value is None:
        return True
    if sense == "MAXIMIZE":
        return candidate_value > incumbent_value
    return candidate_value < incumbent_value


def _can_beat(
    bound: float,
    incumbent_value: float | None,
    *,
    sense: str,
    tolerance: float = 1e-12,
) -> bool:
    if incumbent_value is None:
        return True
    if sense == "MAXIMIZE":
        return bound > incumbent_value + tolerance
    return bound < incumbent_value - tolerance


def solve_empire_branch_bound(
    problem: Mapping[str, Any],
    *,
    max_wall_clock_ms: Any = None,
    max_nodes: int = 2_000_000,
) -> dict[str, Any]:
    """Solve a bounded binary linear problem using Empire branch-and-bound."""
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

    raw_variables = [
        _text(row.get("variable"))
        for row in (problem.get("variables") or ())
        if isinstance(row, Mapping) and _text(row.get("variable"))
    ]
    variables = sorted(set(raw_variables))
    if not variables:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "no_variables",
            "execution_authority": "none",
        }

    coefficients = {
        variable: _number(
            dict(objective.get("linear") or {}).get(variable, 0.0),
            f"objective:{variable}",
        )
        for variable in variables
    }
    try:
        constraints = _constraints(problem)
    except ValueError as exc:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "constraint_not_supported",
            "detail": str(exc),
            "execution_authority": "none",
        }

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
        budget_ms = _number(raw_budget, "max_wall_clock_ms")
    except ValueError as exc:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "time_budget_invalid",
            "detail": str(exc),
            "execution_authority": "none",
        }
    if budget_ms <= 0:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "time_budget_must_be_positive",
            "execution_authority": "none",
        }
    if max_nodes <= 0:
        raise ValueError("max_nodes must be positive")

    participation = {variable: 0.0 for variable in variables}
    for constraint in constraints:
        for variable, coefficient in constraint.coefficients.items():
            if variable in participation:
                participation[variable] += abs(coefficient)

    ordered = sorted(
        variables,
        key=lambda variable: (
            -abs(coefficients.get(variable, 0.0)),
            -participation.get(variable, 0.0),
            variable,
        ),
    )

    started = time.perf_counter()
    deadline = started + (budget_ms / 1000.0)
    incumbent_assignment: dict[str, int] | None = None
    incumbent_value: float | None = None
    explored_nodes = 0
    pruned_objective = 0
    pruned_constraints = 0
    timed_out = False

    # Stack entries: (index, assignment, objective_partial).
    stack: list[tuple[int, dict[str, int], float]] = [(0, {}, 0.0)]

    while stack:
        if explored_nodes >= max_nodes or time.perf_counter() >= deadline:
            timed_out = True
            break

        index, assignment, partial_value = stack.pop()
        explored_nodes += 1
        remaining = set(ordered[index:])

        possible = all(
            _partial_constraint_possible(
                constraint,
                assignment,
                remaining,
            )
            for constraint in constraints
        )
        if not possible:
            pruned_constraints += 1
            continue

        bound = _objective_bound(
            current_value=partial_value,
            remaining=remaining,
            coefficients=coefficients,
            sense=sense,
        )
        if not _can_beat(bound, incumbent_value, sense=sense):
            pruned_objective += 1
            continue

        if index >= len(ordered):
            feasible, _ = _fully_feasible(constraints, assignment)
            if not feasible:
                pruned_constraints += 1
                continue
            value = _objective_value(coefficients, assignment)
            if _better(value, incumbent_value, sense=sense):
                incumbent_value = value
                incumbent_assignment = dict(assignment)
            elif value == incumbent_value and incumbent_assignment is not None:
                candidate_signature = tuple(
                    variable
                    for variable in sorted(variables)
                    if assignment.get(variable) == 1
                )
                incumbent_signature = tuple(
                    variable
                    for variable in sorted(variables)
                    if incumbent_assignment.get(variable) == 1
                )
                if candidate_signature < incumbent_signature:
                    incumbent_assignment = dict(assignment)
            continue

        variable = ordered[index]
        coefficient = coefficients.get(variable, 0.0)

        # Push less-preferred branch first because stack is LIFO.
        if sense == "MAXIMIZE":
            preferred = 1 if coefficient >= 0 else 0
        else:
            preferred = 1 if coefficient <= 0 else 0
        branch_values = (1 - preferred, preferred)

        for value in branch_values:
            child = dict(assignment)
            child[variable] = value
            stack.append((
                index + 1,
                child,
                partial_value + coefficient * value,
            ))

    wall_clock_ms = (time.perf_counter() - started) * 1000.0

    if incumbent_assignment is None or incumbent_value is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE" if timed_out else "INFEASIBLE",
            "solve_status": (
                "TIME_LIMIT_NO_FEASIBLE"
                if timed_out
                else "INFEASIBLE"
            ),
            "problem_fingerprint": problem.get("problem_fingerprint"),
            "solver": "empire_branch_bound",
            "solver_family": "empire_classical_branch_bound",
            "hardware_class": "cpu",
            "explored_nodes": explored_nodes,
            "pruned_objective_nodes": pruned_objective,
            "pruned_constraint_nodes": pruned_constraints,
            "wall_clock_ms": round(wall_clock_ms, 6),
            "time_budget_ms": budget_ms,
            "optimal_for_normalized_problem": not timed_out,
            "compute_cost_minor_units": None,
            "compute_cost_known": False,
            "external": False,
            "external_solver_called": False,
            "execution_authority": "none",
        }

    feasible, violations = _fully_feasible(
        constraints,
        incumbent_assignment,
    )
    solve_status = "TIME_LIMIT_FEASIBLE" if timed_out else "OPTIMAL"

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE",
        "solve_status": solve_status,
        "problem_fingerprint": problem.get("problem_fingerprint"),
        "solver": "empire_branch_bound",
        "solver_family": "empire_classical_branch_bound",
        "hardware_class": "cpu",
        "assignment": incumbent_assignment,
        "selected_variables": sorted(
            variable
            for variable, value in incumbent_assignment.items()
            if value == 1
        ),
        "selected_count": sum(incumbent_assignment.values()),
        "objective_value": round(float(incumbent_value), 8),
        "constraints_satisfied": feasible,
        "constraint_violation_count": len(violations),
        "constraint_violations": violations,
        "explored_nodes": explored_nodes,
        "pruned_objective_nodes": pruned_objective,
        "pruned_constraint_nodes": pruned_constraints,
        "wall_clock_ms": round(wall_clock_ms, 6),
        "time_budget_ms": budget_ms,
        "max_nodes": int(max_nodes),
        "optimal_for_normalized_problem": not timed_out,
        "compute_cost_minor_units": None,
        "compute_cost_known": False,
        "external": False,
        "external_solver_called": False,
        "prediction_only": True,
        "actual_revenue": False,
        "production_promotion_ready": False,
        "execution_authority": "none",
    }
