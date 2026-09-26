"""Strategic scenario planning for Empire Strategy.

Scenarios are structured hypotheticals, not forecasts. This module provides
stress-testing and response planning with no execution authority.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping


SCENARIO_TYPES = {
    "market_demand",
    "buyer_capacity",
    "competitor",
    "search_ai_behavior",
    "model_cost",
    "data_source",
    "regulation",
    "infrastructure",
    "pricing",
    "partner_distribution",
}

IMPACT_DIMENSIONS = (
    "demand",
    "buyer_capacity",
    "gross_margin",
    "search_visibility",
    "ai_visibility",
    "data_availability",
    "model_cost",
    "regulatory_friction",
    "competitive_pressure",
    "time_to_revenue",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bounded(value: Any, name: str) -> float | None:
    x = _number(value)
    if x is None:
        return None
    if not 0 <= x <= 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return x


def _impact(value: Any, name: str) -> float | None:
    x = _number(value)
    if x is None:
        return None
    if not -1 <= x <= 1:
        raise ValueError(f"{name} impact must be between -1 and 1")
    return x


def review_scenario(raw: Mapping[str, Any]) -> dict[str, Any]:
    scenario_id = _text(raw.get("scenario_id"))
    scenario_type = _text(raw.get("scenario_type")).lower()
    title = _text(raw.get("title"))
    hypothesis = _text(raw.get("hypothesis"))
    evidence_refs = [_text(x) for x in raw.get("evidence_refs", ()) if _text(x)]
    probability = _bounded(raw.get("estimated_probability"), "estimated_probability")
    confidence = _bounded(raw.get("confidence"), "confidence")
    time_horizon_days = _number(raw.get("time_horizon_days"))

    blockers: list[str] = []
    if not scenario_id:
        blockers.append("scenario_id_required")
    if scenario_type not in SCENARIO_TYPES:
        blockers.append("unsupported_scenario_type")
    if not title:
        blockers.append("title_required")
    if not hypothesis:
        blockers.append("hypothesis_required")
    if not evidence_refs:
        blockers.append("evidence_refs_required")
    if time_horizon_days is not None and time_horizon_days < 0:
        blockers.append("time_horizon_days_must_be_nonnegative")

    impacts = {}
    for dimension in IMPACT_DIMENSIONS:
        impacts[dimension] = _impact(raw.get("impacts", {}).get(dimension), dimension)

    observed_impacts = {k: v for k, v in impacts.items() if v is not None}
    if not observed_impacts:
        blockers.append("at_least_one_impact_required")

    response_options = []
    for option in raw.get("response_options", ()) or ():
        if not isinstance(option, Mapping):
            continue
        option_id = _text(option.get("option_id"))
        summary = _text(option.get("summary"))
        reversible = option.get("reversible")
        evidence = [_text(x) for x in option.get("evidence_refs", ()) if _text(x)]
        if option_id and summary:
            response_options.append({
                "option_id": option_id,
                "summary": summary,
                "reversible": reversible is True,
                "evidence_refs": evidence,
            })

    return {
        "schema_version": "strategic_scenario.v1",
        "scenario_id": scenario_id or None,
        "scenario_type": scenario_type or None,
        "title": title or None,
        "hypothesis": hypothesis or None,
        "time_horizon_days": time_horizon_days,
        "estimated_probability": probability,
        "confidence": confidence,
        "impacts": impacts,
        "response_options": response_options,
        "evidence_refs": evidence_refs,
        "review_ready": not blockers,
        "blockers": blockers,
        "scenario_only": True,
        "forecast": False,
        "actual_outcome": False,
        "execution_authority": "none",
    }


def build_scenario_set(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    scenarios = []
    seen: set[str] = set()

    for raw in rows:
        scenario = review_scenario(raw)
        sid = scenario["scenario_id"]
        if sid:
            if sid in seen:
                raise ValueError("duplicate scenario_id")
            seen.add(sid)
        scenarios.append(scenario)

    probabilities = [
        row["estimated_probability"]
        for row in scenarios
        if row["estimated_probability"] is not None
    ]
    all_probabilities_present = bool(scenarios) and len(probabilities) == len(scenarios)
    probability_sum = sum(probabilities) if all_probabilities_present else None
    probability_set_valid = (
        all_probabilities_present and abs(probability_sum - 1.0) <= 0.02
    )

    expected_impacts = {dimension: None for dimension in IMPACT_DIMENSIONS}
    if probability_set_valid:
        for dimension in IMPACT_DIMENSIONS:
            if all(row["impacts"][dimension] is not None for row in scenarios):
                expected_impacts[dimension] = round(
                    sum(
                        row["estimated_probability"] * row["impacts"][dimension]
                        for row in scenarios
                    ),
                    6,
                )

    return {
        "schema_version": "strategic_scenario_set.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "scenarios": scenarios,
        "all_probabilities_present": all_probabilities_present,
        "probability_sum": round(probability_sum, 6) if probability_sum is not None else None,
        "probability_set_valid": probability_set_valid,
        "expected_impacts": expected_impacts,
        "scenario_only": True,
        "forecast": False,
        "execution_enabled": False,
    }


def stress_test_strategy(
    *,
    baseline: Mapping[str, Any],
    scenarios: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Apply scenario impact factors to normalized baseline resilience dimensions."""
    baseline_values = {}
    for dimension in IMPACT_DIMENSIONS:
        raw = baseline.get(dimension)
        if raw is None:
            baseline_values[dimension] = None
        else:
            baseline_values[dimension] = _bounded(raw, f"baseline:{dimension}")

    scenario_set = build_scenario_set(scenarios)
    results = []

    for scenario in scenario_set["scenarios"]:
        projected = {}
        missing = []
        for dimension in IMPACT_DIMENSIONS:
            base = baseline_values[dimension]
            impact = scenario["impacts"][dimension]
            if base is None or impact is None:
                projected[dimension] = None
                if impact is not None and base is None:
                    missing.append(f"baseline:{dimension}")
                continue
            # For adverse dimensions (cost/friction/pressure/time) higher is worse,
            # but this function only applies normalized directional stress. Consumers
            # interpret dimension semantics explicitly.
            projected[dimension] = round(min(1.0, max(0.0, base * (1 + impact))), 6)

        adverse_impacts = [
            abs(value)
            for key, value in scenario["impacts"].items()
            if value is not None and (
                (key in {"demand","buyer_capacity","gross_margin","search_visibility","ai_visibility","data_availability"} and value < 0)
                or (key in {"model_cost","regulatory_friction","competitive_pressure","time_to_revenue"} and value > 0)
            )
        ]
        stress_severity = (
            round(sum(adverse_impacts) / len(adverse_impacts), 6)
            if adverse_impacts else 0.0
        )

        results.append({
            "scenario_id": scenario["scenario_id"],
            "scenario_type": scenario["scenario_type"],
            "projected_normalized_state": projected,
            "missing_baseline": sorted(set(missing)),
            "stress_severity": stress_severity,
            "response_options": scenario["response_options"],
            "scenario_only": True,
        })

    results.sort(
        key=lambda row: (row["stress_severity"], row["scenario_id"] or ""),
        reverse=True,
    )
    for idx, row in enumerate(results, 1):
        row["stress_rank"] = idx

    return {
        "schema_version": "strategic_stress_test.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "baseline": baseline_values,
        "scenario_set": scenario_set,
        "stress_results": results,
        "scenario_only": True,
        "forecast": False,
        "execution_enabled": False,
    }


def scenario_gaps(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    scenario_set = build_scenario_set(rows)
    represented = {
        row["scenario_type"]
        for row in scenario_set["scenarios"]
        if row["scenario_type"] in SCENARIO_TYPES
    }
    missing_types = sorted(SCENARIO_TYPES - represented)
    invalid = [
        row["scenario_id"]
        for row in scenario_set["scenarios"]
        if not row["review_ready"]
    ]
    return {
        "schema_version": "strategic_scenario_gaps.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "represented_types": sorted(represented),
        "missing_scenario_types": missing_types,
        "invalid_scenarios": invalid,
        "forecast": False,
    }
