"""Generic exact binary solver for Empire Optimization IR.

This is the universal small-problem classical reference. It supports linear
binary problems with explicit hard constraints and is intentionally bounded by
a variable limit. It never performs external actions.
"""
from __future__ import annotations

from itertools import product
from typing import Any, Mapping
import time

from empire_os.optimization_problem_factory import validate_problem_integrity


SCHEMA_VERSION = "empire.solver_adapter.exact_binary.v1"
DEFAULT_MAX_VARIABLES = 18


def _text(value: Any) -> str:
    return str(value or "").strip()


def _objective_value(
    objective: Mapping[str, Any],
    assignment: Mapping[str, int],
) -> float:
    linear = dict(objective.get("linear") or {})
    quadratic = dict(objective.get("quadratic") or {})
    value = sum(
        float(coefficient) * int(assignment.get(str(variable), 0))
        for variable, coefficient in linear.items()
    )
    for raw_key, coefficient in quadratic.items():
        key = str(raw_key)
        if "|" not in key:
            raise ValueError("quadratic key must be left|right")
        left, right = key.split("|", 1)
        value += (
            float(coefficient)
            * int(assignment.get(left, 0))
            * int(assignment.get(right, 0))
        )
    return value


def _constraints_satisfied(
    constraints: list[Mapping[str, Any]],
    assignment: Mapping[str, int],
    *,
    tolerance: float = 1e-9,
) -> tuple[bool, list[dict[str, Any]]]:
    violations: list[dict[str, Any]] = []
    for raw in constraints:
        name = _text(raw.get("name")) or "unnamed"
        coefficients = dict(raw.get("coefficients") or {})
        lhs = sum(
            float(coefficient) * int(assignment.get(str(variable), 0))
            for variable, coefficient in coefficients.items()
        )
        rhs = float(raw.get("rhs"))
        sense = _text(raw.get("sense"))
        ok = (
            lhs <= rhs + tolerance
            if sense == "<="
            else lhs >= rhs - tolerance
            if sense == ">="
            else abs(lhs - rhs) <= tolerance
            if sense in {"==", "="}
            else False
        )
        if not ok:
            violations.append({
                "constraint": name,
                "lhs": lhs,
                "sense": sense,
                "rhs": rhs,
            })
    return not violations, violations


def solve_exact_binary(
    problem: Mapping[str, Any],
    *,
    max_variables: int = DEFAULT_MAX_VARIABLES,
) -> dict[str, Any]:
    """Exhaustively solve one bounded binary Empire Optimization IR problem."""
    if max_variables <= 0:
        raise ValueError("max_variables must be positive")
    if str(problem.get("status") or "").upper() != "AVAILABLE":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "optimization_problem_unavailable",
            "execution_authority": "none",
        }
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

    variables = [
        str(row.get("variable") or "").strip()
        for row in (problem.get("variables") or ())
        if isinstance(row, Mapping)
    ]
    variables = [value for value in variables if value]
    if len(set(variables)) != len(variables):
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "duplicate_variable_identity",
            "execution_authority": "none",
        }
    if not variables:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "no_variables",
            "execution_authority": "none",
        }
    if len(variables) > max_variables:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "exact_reference_variable_limit_exceeded",
            "variable_count": len(variables),
            "max_variables": max_variables,
            "execution_authority": "none",
        }

    objective = dict(problem.get("objective") or {})
    sense = _text(objective.get("sense")).upper()
    if sense not in {"MAXIMIZE", "MINIMIZE"}:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "unsupported_objective_sense",
            "execution_authority": "none",
        }
    constraints = [
        dict(row)
        for row in (problem.get("constraints") or ())
        if isinstance(row, Mapping)
    ]

    best_assignment: dict[str, int] | None = None
    best_value: float | None = None
    feasible_states = 0
    explored_states = 0
    started = time.perf_counter()

    for bits in product((0, 1), repeat=len(variables)):
        explored_states += 1
        assignment = dict(zip(variables, bits, strict=True))
        feasible, _ = _constraints_satisfied(constraints, assignment)
        if not feasible:
            continue
        feasible_states += 1
        value = _objective_value(objective, assignment)
        signature = tuple(
            name
            for name in sorted(variables)
            if assignment[name] == 1
        )
        best_signature = (
            tuple(
                name
                for name in sorted(variables)
                if best_assignment and best_assignment.get(name) == 1
            )
            if best_assignment is not None
            else None
        )
        better = (
            best_value is None
            or (sense == "MAXIMIZE" and value > best_value)
            or (sense == "MINIMIZE" and value < best_value)
            or (
                value == best_value
                and best_signature is not None
                and signature < best_signature
            )
        )
        if better:
            best_value = value
            best_assignment = assignment

    observed_wall_ms = (time.perf_counter() - started) * 1000.0

    if best_assignment is None or best_value is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "INFEASIBLE",
            "problem_fingerprint": problem.get("problem_fingerprint"),
            "solver": "classical_exact_binary_ir",
            "solver_family": "classical_exact",
            "optimal_for_normalized_problem": True,
            "explored_states": explored_states,
            "feasible_states": 0,
            "wall_clock_ms": round(observed_wall_ms, 6),
            "execution_authority": "none",
        }

    selected = sorted(
        name
        for name, value in best_assignment.items()
        if value == 1
    )
    valid, violations = _constraints_satisfied(
        constraints,
        best_assignment,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE",
        "problem_fingerprint": problem.get("problem_fingerprint"),
        "solver": "classical_exact_binary_ir",
        "solver_family": "classical_exact",
        "hardware_class": "cpu",
        "assignment": best_assignment,
        "selected_variables": selected,
        "selected_count": len(selected),
        "objective_value": round(float(best_value), 8),
        "constraints_satisfied": valid,
        "constraint_violation_count": len(violations),
        "constraint_violations": violations,
        "optimal_for_normalized_problem": True,
        "explored_states": explored_states,
        "feasible_states": feasible_states,
        "wall_clock_ms": round(observed_wall_ms, 6),
        "compute_cost_minor_units": None,
        "compute_cost_known": False,
        "external": False,
        "external_solver_called": False,
        "prediction_only": True,
        "actual_revenue": False,
        "production_promotion_ready": False,
        "execution_authority": "none",
    }
