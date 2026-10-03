"""Safe monotone greedy heuristic for Empire Optimization IR."""
from __future__ import annotations
from typing import Any, Mapping
import time

SCHEMA_VERSION = "empire.solver_adapter.greedy_binary.v1"

def _text(value: Any) -> str:
    return str(value or "").strip()

def is_safe_monotone_greedy_problem(problem: Mapping[str, Any]) -> bool:
    if str(problem.get("status") or "").upper() != "AVAILABLE":
        return False
    if _text(problem.get("variable_type")).upper() != "BINARY":
        return False
    objective = dict(problem.get("objective") or {})
    if _text(objective.get("sense")).upper() != "MAXIMIZE":
        return False
    if dict(objective.get("quadratic") or {}):
        return False
    try:
        if any(float(v) < 0 for v in dict(objective.get("linear") or {}).values()):
            return False
        for raw in problem.get("constraints") or ():
            if not isinstance(raw, Mapping) or _text(raw.get("sense")) != "<=":
                return False
            if float(raw.get("rhs")) < 0:
                return False
            if any(float(v) < 0 for v in dict(raw.get("coefficients") or {}).values()):
                return False
    except (TypeError, ValueError):
        return False
    return True

def _feasible(constraints, assignment):
    for raw in constraints:
        lhs = sum(float(c) * int(assignment.get(str(v), 0))
                  for v, c in dict(raw.get("coefficients") or {}).items())
        if lhs > float(raw.get("rhs")) + 1e-9:
            return False
    return True

def solve_greedy_binary(problem: Mapping[str, Any]) -> dict[str, Any]:
    if not is_safe_monotone_greedy_problem(problem):
        return {"schema_version": SCHEMA_VERSION, "status": "UNAVAILABLE",
                "reason": "problem_outside_safe_monotone_greedy_scope",
                "execution_authority": "none"}
    objective = dict(problem.get("objective") or {})
    coeffs = {str(v): float(c) for v, c in dict(objective.get("linear") or {}).items()}
    variables = sorted(
        (_text(r.get("variable")) for r in (problem.get("variables") or ())
         if isinstance(r, Mapping) and _text(r.get("variable"))),
        key=lambda v: (-coeffs.get(v, 0.0), v),
    )
    constraints = [dict(r) for r in (problem.get("constraints") or ()) if isinstance(r, Mapping)]
    assignment = {v: 0 for v in variables}
    started = time.perf_counter()
    for variable in variables:
        if coeffs.get(variable, 0.0) <= 0:
            continue
        assignment[variable] = 1
        if not _feasible(constraints, assignment):
            assignment[variable] = 0
    wall = (time.perf_counter() - started) * 1000.0
    feasible = _feasible(constraints, assignment)
    value = sum(coeffs.get(v, 0.0) * x for v, x in assignment.items())
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE" if feasible else "UNAVAILABLE",
        "reason": None if feasible else "post_solve_constraint_violation",
        "problem_fingerprint": problem.get("problem_fingerprint"),
        "solver": "classical_greedy_binary_ir",
        "solver_family": "classical_greedy",
        "hardware_class": "cpu",
        "assignment": assignment,
        "selected_variables": sorted(v for v, x in assignment.items() if x == 1),
        "selected_count": sum(assignment.values()),
        "objective_value": round(value, 8),
        "constraints_satisfied": feasible,
        "optimal_for_normalized_problem": False,
        "wall_clock_ms": round(wall, 6),
        "compute_cost_minor_units": None,
        "compute_cost_known": False,
        "external": False,
        "external_solver_called": False,
        "prediction_only": True,
        "actual_revenue": False,
        "production_promotion_ready": False,
        "execution_authority": "none",
    }
