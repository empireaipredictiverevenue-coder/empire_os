"""Shared Empire-owned QUBO math and truth-boundary helpers."""
from __future__ import annotations

from typing import Any, Mapping


def text(value: Any) -> str:
    return str(value or "").strip()


def number(value: Any, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if result != result or result in (float("inf"), float("-inf")):
        raise ValueError(f"{name} must be finite")
    return result


def parse_quadratic(
    raw: Mapping[str, Any],
) -> tuple[
    dict[tuple[str, str], float],
    dict[str, list[tuple[str, float]]],
]:
    quadratic: dict[tuple[str, str], float] = {}
    adjacency: dict[str, list[tuple[str, float]]] = {}
    for raw_key, raw_coefficient in raw.items():
        key = str(raw_key)
        left, separator, right = key.partition("|")
        if not separator or not left or not right:
            raise ValueError(f"invalid QUBO quadratic key:{key}")
        coefficient = number(raw_coefficient, f"quadratic:{key}")
        pair = tuple(sorted((left, right)))
        quadratic[pair] = quadratic.get(pair, 0.0) + coefficient

    for (left, right), coefficient in quadratic.items():
        adjacency.setdefault(left, []).append((right, coefficient))
        if right != left:
            adjacency.setdefault(right, []).append((left, coefficient))
    return quadratic, adjacency


def variable_order(
    linear: Mapping[str, float],
    quadratic: Mapping[tuple[str, str], float],
) -> list[str]:
    variables = set(map(str, linear))
    for left, right in quadratic:
        variables.add(left)
        variables.add(right)
    return sorted(variables)


def energy(
    assignment: Mapping[str, int],
    linear: Mapping[str, float],
    quadratic: Mapping[tuple[str, str], float],
) -> float:
    result = sum(
        coefficient * int(assignment.get(variable, 0))
        for variable, coefficient in linear.items()
    )
    for (left, right), coefficient in quadratic.items():
        result += (
            coefficient
            * int(assignment.get(left, 0))
            * int(assignment.get(right, 0))
        )
    return result


def flip_delta(
    variable: str,
    assignment: Mapping[str, int],
    linear: Mapping[str, float],
    adjacency: Mapping[str, list[tuple[str, float]]],
) -> float:
    current = int(assignment.get(variable, 0))
    local_field = linear.get(variable, 0.0)
    for other, coefficient in adjacency.get(variable, ()):
        if other == variable:
            local_field += coefficient
        else:
            local_field += coefficient * int(assignment.get(other, 0))
    return (1 - (2 * current)) * local_field


def validate_constraints(
    qubo: Mapping[str, Any],
    assignment: Mapping[str, int],
    *,
    tolerance: float = 1e-9,
) -> tuple[bool, list[dict[str, Any]]]:
    violations: list[dict[str, Any]] = []
    for raw in qubo.get("source_constraints") or ():
        if not isinstance(raw, Mapping):
            continue
        coefficients = dict(raw.get("coefficients") or {})
        lhs = sum(
            number(coefficient, f"constraint:{variable}")
            * int(assignment.get(str(variable), 0))
            for variable, coefficient in coefficients.items()
        )
        rhs = number(raw.get("rhs"), "constraint rhs")
        sense = text(raw.get("sense"))
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
                "constraint": raw.get("name"),
                "lhs": lhs,
                "sense": sense,
                "rhs": rhs,
            })
    return not violations, violations


def source_objective(
    qubo: Mapping[str, Any],
    assignment: Mapping[str, int],
) -> float:
    objective = dict(qubo.get("source_objective") or {})
    linear = {
        str(variable): number(
            coefficient,
            f"source objective:{variable}",
        )
        for variable, coefficient in dict(
            objective.get("linear") or {}
        ).items()
    }
    quadratic, _ = parse_quadratic(
        dict(objective.get("quadratic") or {})
    )
    return energy(assignment, linear, quadratic)


def source_sense(qubo: Mapping[str, Any]) -> str:
    return text(
        dict(qubo.get("source_objective") or {}).get("sense")
    ).upper()


def assignment_from_index(
    index: int,
    variables: list[str],
) -> dict[str, int]:
    return {
        variable: (index >> position) & 1
        for position, variable in enumerate(variables)
    }


def index_from_assignment(
    assignment: Mapping[str, int],
    variables: list[str],
) -> int:
    result = 0
    for position, variable in enumerate(variables):
        if int(assignment.get(variable, 0)):
            result |= 1 << position
    return result
