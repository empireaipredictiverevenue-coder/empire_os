"""Google OR-Tools CP-SAT adapter for Empire Optimization IR.

The adapter is optional and lazily imports OR-Tools. It supports bounded binary,
linear optimization problems only in this first slice. Every returned solution
is independently checked against the original unscaled Empire constraints.

No commercial action is executed and compute cost stays UNKNOWN unless a future
runtime supplies observed cost evidence.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping
import time


SCHEMA_VERSION = "empire.solver_adapter.ortools_cp_sat.v1"
MAX_DECIMAL_PLACES = 8
MAX_ABS_SCALED_TERM = 9_000_000_000_000_000


def _text(value: Any) -> str:
    return str(value or "").strip()


def _decimal(value: Any, name: str) -> Decimal:
    if value is None:
        raise ValueError(f"{name} required")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not number.is_finite():
        raise ValueError(f"{name} must be finite")
    return number


def _scale_values(
    values: list[Decimal],
    *,
    name: str,
) -> tuple[int, list[int]]:
    places = max(
        [max(0, -value.as_tuple().exponent) for value in values]
        or [0]
    )
    if places > MAX_DECIMAL_PLACES:
        raise ValueError(
            f"{name} precision exceeds {MAX_DECIMAL_PLACES} decimal places"
        )
    scale = 10 ** places
    integers: list[int] = []
    for value in values:
        scaled = value * scale
        if scaled != scaled.to_integral_value():
            raise ValueError(f"{name} cannot be represented exactly")
        integer = int(scaled)
        if abs(integer) > MAX_ABS_SCALED_TERM:
            raise ValueError(f"{name} exceeds safe CP-SAT integer range")
        integers.append(integer)
    if sum(abs(value) for value in integers) > MAX_ABS_SCALED_TERM:
        raise ValueError(f"{name} aggregate exceeds safe CP-SAT integer range")
    return scale, integers


def _load_cp_model():
    try:
        from ortools.sat.python import cp_model
    except ImportError:
        return None
    return cp_model


def _validate_assignment(
    problem: Mapping[str, Any],
    assignment: Mapping[str, int],
    *,
    tolerance: float = 1e-7,
) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    for raw in problem.get("constraints") or ():
        if not isinstance(raw, Mapping):
            continue
        name = _text(raw.get("name")) or "unnamed"
        coefficients = dict(raw.get("coefficients") or {})
        lhs = sum(
            float(coefficient) * int(assignment.get(str(variable), 0))
            for variable, coefficient in coefficients.items()
        )
        rhs = float(raw.get("rhs"))
        sense = _text(raw.get("sense"))
        satisfied = (
            lhs <= rhs + tolerance
            if sense == "<="
            else lhs >= rhs - tolerance
            if sense == ">="
            else abs(lhs - rhs) <= tolerance
            if sense in {"==", "="}
            else False
        )
        if not satisfied:
            violations.append({
                "constraint": name,
                "lhs": lhs,
                "sense": sense,
                "rhs": rhs,
            })
    return {
        "constraints_satisfied": not violations,
        "constraint_violation_count": len(violations),
        "constraint_violations": violations,
    }


def _objective_value(
    problem: Mapping[str, Any],
    assignment: Mapping[str, int],
) -> float:
    objective = dict(problem.get("objective") or {})
    linear = dict(objective.get("linear") or {})
    return sum(
        float(coefficient) * int(assignment.get(str(variable), 0))
        for variable, coefficient in linear.items()
    )


def solve_cp_sat(
    problem: Mapping[str, Any],
    *,
    max_wall_clock_ms: Any = None,
    max_workers: int = 1,
    random_seed: int = 0,
) -> dict[str, Any]:
    """Solve one bounded binary-linear Empire Optimization IR problem."""
    if str(problem.get("status") or "").upper() != "AVAILABLE":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "optimization_problem_unavailable",
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
            "reason": "quadratic_objective_not_supported_by_cp_sat_adapter_v1",
            "execution_authority": "none",
        }

    budget_ms = (
        max_wall_clock_ms
        if max_wall_clock_ms is not None
        else problem.get("time_budget_ms")
    )
    if budget_ms is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "time_budget_required",
            "execution_authority": "none",
        }
    try:
        budget_ms = float(budget_ms)
    except (TypeError, ValueError):
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "time_budget_invalid",
            "execution_authority": "none",
        }
    if budget_ms <= 0:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "time_budget_must_be_positive",
            "execution_authority": "none",
        }
    if int(max_workers) <= 0:
        raise ValueError("max_workers must be positive")

    cp_model = _load_cp_model()
    if cp_model is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "ortools_not_installed",
            "external_solver_called": False,
            "execution_authority": "none",
        }

    variables = [
        dict(row)
        for row in (problem.get("variables") or ())
        if isinstance(row, Mapping)
    ]
    if not variables:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "no_variables",
            "execution_authority": "none",
        }

    model = cp_model.CpModel()
    cp_variables = {
        str(row["variable"]): model.new_bool_var(str(row["variable"]))
        for row in variables
    }

    try:
        linear = dict(objective.get("linear") or {})
        objective_names = list(linear)
        objective_decimals = [
            _decimal(linear[name], f"objective:{name}")
            for name in objective_names
        ]
        objective_scale, objective_ints = _scale_values(
            objective_decimals,
            name="objective",
        )
        objective_expr = sum(
            coefficient * cp_variables[name]
            for name, coefficient in zip(
                objective_names,
                objective_ints,
                strict=True,
            )
        )
        sense = _text(objective.get("sense")).upper()
        if sense == "MAXIMIZE":
            model.maximize(objective_expr)
        elif sense == "MINIMIZE":
            model.minimize(objective_expr)
        else:
            raise ValueError("unsupported objective sense")

        for raw in problem.get("constraints") or ():
            if not isinstance(raw, Mapping):
                continue
            name = _text(raw.get("name")) or "constraint"
            coefficients = dict(raw.get("coefficients") or {})
            names = list(coefficients)
            decimals = [
                _decimal(coefficients[var], f"constraint:{name}:{var}")
                for var in names
            ]
            rhs_decimal = _decimal(
                raw.get("rhs"),
                f"constraint:{name}:rhs",
            )
            scale, integers = _scale_values(
                [*decimals, rhs_decimal],
                name=f"constraint:{name}",
            )
            coefficient_ints = integers[:-1]
            rhs_int = integers[-1]
            expr = sum(
                coefficient * cp_variables[var]
                for var, coefficient in zip(
                    names,
                    coefficient_ints,
                    strict=True,
                )
            )
            constraint_sense = _text(raw.get("sense"))
            if constraint_sense == "<=":
                model.add(expr <= rhs_int)
            elif constraint_sense == ">=":
                model.add(expr >= rhs_int)
            elif constraint_sense in {"==", "="}:
                model.add(expr == rhs_int)
            else:
                raise ValueError(
                    f"unsupported constraint sense:{constraint_sense}"
                )
            del scale
    except (KeyError, ValueError) as exc:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "problem_not_representable_by_cp_sat_adapter_v1",
            "detail": str(exc),
            "external_solver_called": False,
            "execution_authority": "none",
        }

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = budget_ms / 1000.0
    solver.parameters.num_search_workers = int(max_workers)
    solver.parameters.random_seed = int(random_seed)

    started = time.perf_counter()
    status_code = solver.solve(model)
    observed_wall_ms = (time.perf_counter() - started) * 1000.0

    status_names = {
        cp_model.OPTIMAL: "OPTIMAL",
        cp_model.FEASIBLE: "FEASIBLE",
        cp_model.INFEASIBLE: "INFEASIBLE",
        cp_model.MODEL_INVALID: "MODEL_INVALID",
        cp_model.UNKNOWN: "UNKNOWN",
    }
    solve_status = status_names.get(status_code, f"STATUS_{status_code}")
    feasible = solve_status in {"OPTIMAL", "FEASIBLE"}

    assignment = (
        {
            name: int(solver.value(variable))
            for name, variable in cp_variables.items()
        }
        if feasible
        else {}
    )
    validation = (
        _validate_assignment(problem, assignment)
        if feasible
        else {
            "constraints_satisfied": False,
            "constraint_violation_count": None,
            "constraint_violations": [],
        }
    )
    original_objective = (
        _objective_value(problem, assignment)
        if feasible
        else None
    )
    selected = sorted(
        name
        for name, value in assignment.items()
        if value == 1
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE" if feasible else solve_status,
        "solve_status": solve_status,
        "problem_fingerprint": problem.get("problem_fingerprint"),
        "solver": "ortools_cp_sat",
        "solver_family": "classical_cp_sat",
        "hardware_class": "cpu",
        "provider": "google_or_tools",
        "assignment": assignment,
        "selected_variables": selected,
        "selected_count": len(selected),
        "objective_value": (
            round(float(original_objective), 8)
            if original_objective is not None
            else None
        ),
        "objective_scale": objective_scale,
        **validation,
        "wall_clock_ms": round(observed_wall_ms, 6),
        "solver_wall_clock_ms": round(
            float(solver.wall_time) * 1000.0,
            6,
        ),
        "time_budget_ms": budget_ms,
        "max_workers": int(max_workers),
        "deterministic_reference_configuration": int(max_workers) == 1,
        "compute_cost_minor_units": None,
        "compute_cost_known": False,
        "external": False,
        "external_solver_called": False,
        "prediction_only": True,
        "actual_revenue": False,
        "production_promotion_ready": False,
        "execution_authority": "none",
    }
