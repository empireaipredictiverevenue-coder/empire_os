"""Scenario-aware Predictive Cloud portfolio optimization compiler.

Predictive Cloud should optimize across explicit plausible futures, not a single
point forecast. This module converts evidence-backed scenarios and action-level
scenario values into the common Empire Optimization IR.

Risk policy is explicit:
  robust_value = (1 - risk_aversion) * expected_value
                 + risk_aversion * worst_case_value

No missing scenario value, probability, cost, capacity or evidence is treated as
zero. The output is recommendation-only and carries no execution authority.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from empire_os.optimization_problem_factory import build_problem_ir


SCHEMA_VERSION = "empire.predictive_cloud.scenario_optimization.v1"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any, name: str) -> float:
    if value is None:
        raise ValueError(f"{name} required")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if number != number or number in (float("inf"), float("-inf")):
        raise ValueError(f"{name} must be finite")
    return number


def _nonnegative(value: Any, name: str) -> float:
    number = _number(value, name)
    if number < 0:
        raise ValueError(f"{name} must be nonnegative")
    return number


def _probability(value: Any, name: str) -> float:
    number = _number(value, name)
    if not 0 <= number <= 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return number


def _evidence(raw: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(sorted({
        _text(ref)
        for ref in (raw.get("evidence_refs") or ())
        if _text(ref)
    }))


def build_predictive_cloud_scenario_problem(
    *,
    scenarios: Sequence[Mapping[str, Any]],
    actions: Sequence[Mapping[str, Any]],
    budget_cents: Any,
    capacity_constraints: Mapping[str, Any] | None = None,
    risk_aversion: Any = 0.25,
    workload_key: str = "predictive_cloud_scenario_portfolio",
    tenant_id: str | None = None,
    probability_tolerance: float = 1e-9,
    time_budget_ms: Any = None,
    cost_budget_minor_units: Any = None,
) -> dict[str, Any]:
    """Compile scenario-conditioned action economics into V2 optimization IR."""
    risk = _probability(risk_aversion, "risk_aversion")
    budget = _nonnegative(budget_cents, "budget_cents")

    scenario_rows: list[dict[str, Any]] = []
    scenario_keys: set[str] = set()
    for raw in scenarios:
        if not isinstance(raw, Mapping):
            raise ValueError("scenarios must be mappings")
        key = _text(raw.get("scenario_key"))
        if not key:
            raise ValueError("scenario_key required")
        if key in scenario_keys:
            raise ValueError(f"duplicate scenario_key: {key}")
        scenario_keys.add(key)
        probability = _probability(
            raw.get("probability"),
            f"scenario probability:{key}",
        )
        refs = _evidence(raw)
        if not refs:
            raise ValueError(f"scenario evidence_refs required: {key}")
        scenario_rows.append({
            "scenario_key": key,
            "probability": probability,
            "evidence_refs": refs,
        })

    if not scenario_rows:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "no_scenarios",
            "unknown_is_zero": False,
            "execution_authority": "none",
        }

    probability_sum = sum(row["probability"] for row in scenario_rows)
    if abs(probability_sum - 1.0) > probability_tolerance:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "scenario_probabilities_must_sum_to_one",
            "observed_probability_sum": round(probability_sum, 12),
            "probability_normalized_implicitly": False,
            "unknown_is_zero": False,
            "execution_authority": "none",
        }

    capacities: dict[str, int] = {}
    for raw_key, raw_value in dict(capacity_constraints or {}).items():
        key = _text(raw_key)
        if not key:
            continue
        try:
            value = int(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"capacity {key} must be a nonnegative integer"
            ) from exc
        if value < 0:
            raise ValueError(f"capacity {key} must be nonnegative")
        capacities[key] = value

    scenario_probability = {
        row["scenario_key"]: row["probability"]
        for row in scenario_rows
    }
    scenario_evidence = {
        row["scenario_key"]: row["evidence_refs"]
        for row in scenario_rows
    }

    variables: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    seen_actions: set[str] = set()

    for raw in actions:
        if not isinstance(raw, Mapping):
            continue
        key = _text(raw.get("action_key"))
        refs = _evidence(raw)
        values = raw.get("scenario_values_cents")
        cost_raw = raw.get("action_cost_cents")
        capacity_group = _text(raw.get("capacity_group")) or None
        missing: list[str] = []

        if not key:
            missing.append("action_key")
        if key and key in seen_actions:
            blocked.append({
                "action_key": key,
                "reason": "duplicate_action_key",
            })
            continue
        if not refs:
            missing.append("evidence_refs")
        if not isinstance(values, Mapping):
            missing.append("scenario_values_cents")
            value_map: dict[str, Any] = {}
        else:
            value_map = dict(values)
            for scenario_key in sorted(scenario_keys):
                if value_map.get(scenario_key) is None:
                    missing.append(
                        f"scenario_values_cents:{scenario_key}"
                    )
        if cost_raw is None:
            missing.append("action_cost_cents")
        if capacity_group and capacity_group not in capacities:
            missing.append("capacity_constraint")

        if missing:
            blocked.append({
                "action_key": key or None,
                "missing_fields": sorted(set(missing)),
                "reason": "unknown_scenario_action_economics_preserved",
            })
            continue

        action_cost = _nonnegative(
            cost_raw,
            f"action_cost_cents:{key}",
        )
        if action_cost > budget:
            blocked.append({
                "action_key": key,
                "reason": "action_exceeds_budget",
            })
            continue

        numeric_values = {
            scenario_key: _number(
                value_map[scenario_key],
                f"scenario value:{key}:{scenario_key}",
            )
            for scenario_key in sorted(scenario_keys)
        }
        expected = sum(
            scenario_probability[scenario_key]
            * numeric_values[scenario_key]
            for scenario_key in sorted(scenario_keys)
        )
        worst_case = min(numeric_values.values())
        robust = ((1.0 - risk) * expected) + (risk * worst_case)

        all_refs = set(refs)
        for scenario_key in scenario_keys:
            all_refs.update(scenario_evidence[scenario_key])

        variables.append({
            "variable": f"x::{key}",
            "action_key": key,
            "expected_value_cents": round(expected, 8),
            "worst_case_value_cents": round(worst_case, 8),
            "robust_value_cents": round(robust, 8),
            "action_cost_cents": action_cost,
            "capacity_group": capacity_group,
            "scenario_values_cents": numeric_values,
            "evidence_refs": tuple(sorted(all_refs)),
        })
        seen_actions.add(key)

    if not variables:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "no_evidence_complete_actions",
            "blocked_actions": blocked,
            "unknown_is_zero": False,
            "execution_authority": "none",
        }

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

    problem = build_problem_ir(
        workload_key=workload_key,
        workload_type="predictive_cloud_scenario_portfolio",
        source_schema_version=SCHEMA_VERSION,
        variable_type="BINARY",
        variables=variables,
        objective={
            "sense": "MAXIMIZE",
            "linear": {
                row["variable"]: row["robust_value_cents"]
                for row in variables
            },
            "quadratic": {},
            "objective_semantics": (
                "maximize_explicit_risk_adjusted_scenario_value_cents"
            ),
        },
        constraints=constraints,
        tenant_id=tenant_id,
        time_budget_ms=time_budget_ms,
        cost_budget_minor_units=cost_budget_minor_units,
        # Budget/general-capacity QUBO needs safe slack/penalty encoding first.
        representations=("CQM",),
        metadata={
            "scenario_count": len(scenario_rows),
            "risk_aversion": risk,
            "risk_policy": (
                "(1-risk_aversion)*expected_value"
                "+risk_aversion*worst_case_value"
            ),
            "budget_cents": budget,
            "capacity_group_count": len(capacities),
            "blocked_actions": blocked,
            "scenario_probabilities_explicit": True,
            "scenario_probabilities_implicitly_normalized": False,
            "qubo_revalidation_required": True,
        },
    )
    problem["scenario_context"] = {
        "scenarios": [
            {
                "scenario_key": row["scenario_key"],
                "probability": row["probability"],
                "evidence_refs": list(row["evidence_refs"]),
            }
            for row in scenario_rows
        ],
        "risk_aversion": risk,
        "probability_sum": round(probability_sum, 12),
        "prediction_only": True,
        "causal_claim": False,
    }
    problem["actual_revenue"] = False
    problem["execution_authority"] = "none"
    return problem
