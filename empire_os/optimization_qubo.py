"""Safe QUBO compiler for a bounded subset of Empire Optimization IR.

V1 only compiles binary linear objectives with unconstrained variables or
hard at-most-one constraints of the form sum(x_i) <= 1. That shape is enough
for unit-capacity assignment style benchmarks and avoids inventing slack
variables or penalty encodings for general capacities/budgets.
"""
from __future__ import annotations

from itertools import combinations
from typing import Any, Mapping

from empire_os.optimization_problem_factory import validate_problem_integrity


SCHEMA_VERSION = "empire.optimization.qubo.v2"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if number != number or number in (float("inf"), float("-inf")):
        raise ValueError(f"{name} must be finite")
    return number


def build_safe_qubo(
    problem: Mapping[str, Any],
    *,
    penalty_multiplier: float = 2.0,
) -> dict[str, Any]:
    """Compile only constraint shapes with a proof-safe pairwise penalty."""
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
        _text(row.get("variable"))
        for row in (problem.get("variables") or ())
        if isinstance(row, Mapping) and _text(row.get("variable"))
    ]
    variable_set = set(variables)
    if not variables:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "no_variables",
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
    if dict(objective.get("quadratic") or {}):
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "quadratic_objective_requires_separate_validation",
            "execution_authority": "none",
        }

    raw_linear = dict(objective.get("linear") or {})
    if set(map(str, raw_linear)) - variable_set:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "objective_references_unknown_variable",
            "execution_authority": "none",
        }
    original_linear = {
        str(variable): _number(coefficient, f"objective:{variable}")
        for variable, coefficient in raw_linear.items()
    }
    scale = max(
        [abs(value) for value in original_linear.values()] + [1.0]
    )
    sign = -1.0 if sense == "MAXIMIZE" else 1.0
    linear = {
        variable: sign * original_linear.get(variable, 0.0) / scale
        for variable in variables
    }

    normalized_constraints: list[dict[str, Any]] = []
    constraint_groups: list[list[str]] = []
    for index, raw in enumerate(problem.get("constraints") or ()):
        if not isinstance(raw, Mapping):
            continue
        name = _text(raw.get("name")) or f"constraint::{index}"
        constraint_type = _text(raw.get("constraint_type")).lower()
        if constraint_type not in {"", "hard"}:
            return {
                "schema_version": SCHEMA_VERSION,
                "status": "UNAVAILABLE",
                "reason": "soft_constraint_not_supported",
                "constraint": name,
                "execution_authority": "none",
            }
        coefficients = dict(raw.get("coefficients") or {})
        sense_value = _text(raw.get("sense"))
        rhs = _number(raw.get("rhs"), f"constraint:{name}:rhs")
        if sense_value != "<=" or rhs != 1.0:
            return {
                "schema_version": SCHEMA_VERSION,
                "status": "UNAVAILABLE",
                "reason": "general_constraint_requires_cqm_or_slack_encoding",
                "constraint": name,
                "execution_authority": "none",
            }
        group: list[str] = []
        for variable, coefficient in coefficients.items():
            variable = str(variable)
            if variable not in variable_set:
                return {
                    "schema_version": SCHEMA_VERSION,
                    "status": "UNAVAILABLE",
                    "reason": "constraint_references_unknown_variable",
                    "constraint": name,
                    "execution_authority": "none",
                }
            if _number(coefficient, f"constraint:{name}:{variable}") != 1.0:
                return {
                    "schema_version": SCHEMA_VERSION,
                    "status": "UNAVAILABLE",
                    "reason": "non_unit_constraint_coefficient_requires_cqm",
                    "constraint": name,
                    "execution_authority": "none",
                }
            group.append(variable)
        group = sorted(set(group))
        normalized_constraints.append({
            "name": name,
            "coefficients": {variable: 1.0 for variable in group},
            "sense": "<=",
            "rhs": 1.0,
            "constraint_type": "hard",
        })
        if len(group) > 1:
            constraint_groups.append(group)

    multiplier = _number(penalty_multiplier, "penalty_multiplier")
    if multiplier <= 1.0:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "penalty_multiplier_must_exceed_one",
            "execution_authority": "none",
        }

    total_objective_range = sum(abs(value) for value in linear.values())
    penalty = multiplier * max(total_objective_range, 1.0)
    quadratic: dict[str, float] = {}
    for group in constraint_groups:
        for left, right in combinations(group, 2):
            key = f"{left}|{right}"
            quadratic[key] = quadratic.get(key, 0.0) + penalty

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE",
        "problem_fingerprint": problem.get("problem_fingerprint"),
        "model_type": "QUBO",
        "objective_sense": "MINIMIZE",
        "linear": {
            key: round(value, 12)
            for key, value in sorted(linear.items())
        },
        "quadratic": {
            key: round(value, 12)
            for key, value in sorted(quadratic.items())
        },
        "normalization_scale": scale,
        "constraint_penalty": round(penalty, 12),
        "penalty_proof_scope": "hard_at_most_one_pairwise_constraints_only",
        "source_objective": {
            "sense": sense,
            "linear": original_linear,
            "quadratic": {},
        },
        "source_constraints": normalized_constraints,
        "qaoa_ready": True,
        "local_bqm_ready": True,
        "external_solver_called": False,
        "prediction_only": True,
        "actual_revenue": False,
        "production_promotion_ready": False,
        "execution_authority": "none",
    }
