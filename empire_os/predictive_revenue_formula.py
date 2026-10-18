"""Canonical Predictive Revenue Formula for EmpireOS.

This module is the commercial equation layer above Quant Brain. It separates:
- opportunity conversion mechanics;
- expected economic value;
- revenue-state truth;
- next-best-action value.

Missing evidence remains UNKNOWN. It is never silently converted to zero.
Predicted, expected, committed, settled and recognized revenue are distinct.
No function in this module grants execution or accounting authority.
"""
from __future__ import annotations

from itertools import combinations
from math import factorial, isfinite, prod
from typing import Any, Mapping, Sequence


CORE_FACTORS = (
    "demand",
    "quality",
    "enrichment",
    "omega_qualification",
    "buyer_match",
    "outreach",
    "conversion",
    "terms",
    "payment",
    "fulfilment",
)

ERV_REQUIRED = (
    "probability_close",
    "probability_payment_given_close",
    "probability_fulfilment_given_payment",
    "ltv_cents",
    "margin_factor",
    "capacity_factor",
    "recency_factor",
    "confidence",
    "time_discount_factor",
    "acquisition_cost_cents",
    "fulfilment_cost_cents",
    "risk_cost_cents",
)

REVENUE_STATES = (
    "opportunity",
    "expected",
    "qualified",
    "proposed",
    "committed",
    "payment_pending",
    "settled",
    "revenue_recognized",
    "fulfilled",
    "retained",
)

STATE_EVIDENCE = {
    "opportunity": ("opportunity_evidence_ref",),
    "expected": ("prediction_evidence_ref",),
    "qualified": ("qualification_evidence_ref",),
    "proposed": ("proposal_evidence_ref",),
    "committed": (
        "commitment_evidence_ref",
        "buyer_identity_evidence_ref",
        "commercial_terms_evidence_ref",
    ),
    "payment_pending": ("payment_request_evidence_ref",),
    "settled": ("settlement_evidence_ref",),
    "revenue_recognized": ("revenue_recognition_evidence_ref",),
    "fulfilled": ("fulfilment_evidence_ref",),
    "retained": ("retention_evidence_ref",),
}


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number, not bool")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _probability(value: Any, name: str) -> float:
    number = _number(value, name)
    if not 0 <= number <= 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return number


def _missing(inputs: Mapping[str, Any], fields: Sequence[str]) -> list[str]:
    return [field for field in fields if inputs.get(field) is None]


def predictive_revenue_formula(
    inputs: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate the canonical multiplicative Predictive Revenue formula.

    R = D*Q*E*Omega*B*O*C*T*P*F*LTV

    Every factor must be evidenced. Missing is UNKNOWN, not zero.
    """
    data = dict(inputs or {})
    required = (*CORE_FACTORS, "ltv_cents")
    missing = _missing(data, required)
    if missing:
        return {
            "schema_version": "empire.predictive_revenue.formula.v1",
            "status": "UNAVAILABLE",
            "missing_fields": missing,
            "reason": "unknown_inputs_preserved",
            "unknown_is_zero": False,
            "prediction_only": True,
            "actual_revenue": False,
            "execution_authority": "none",
        }

    factors = {
        name: _probability(data[name], name)
        for name in CORE_FACTORS
    }
    ltv_cents = _number(data["ltv_cents"], "ltv_cents")
    if ltv_cents < 0:
        raise ValueError("ltv_cents must be nonnegative")

    joint_probability = prod(factors.values())
    predicted_revenue_cents = joint_probability * ltv_cents
    weakest_factor = min(
        factors.items(),
        key=lambda item: (item[1], item[0]),
    )

    return {
        "schema_version": "empire.predictive_revenue.formula.v1",
        "status": "AVAILABLE",
        "formula": "D*Q*E*OMEGA*B*O*C*T*P*F*LTV",
        "factors": factors,
        "ltv_cents": ltv_cents,
        "joint_success_probability": round(joint_probability, 12),
        "predicted_revenue_cents": round(predicted_revenue_cents, 4),
        "weakest_factor": {
            "name": weakest_factor[0],
            "value": weakest_factor[1],
        },
        "multiplicative_failure_semantics": (
            "any_evidenced_zero_critical_factor_collapses_predicted_revenue"
        ),
        "unknown_is_zero": False,
        "prediction_only": True,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def expected_revenue_value(
    inputs: Mapping[str, Any],
) -> dict[str, Any]:
    """Calculate evidence-adjusted expected revenue value (ERV).

    ERV =
      P(close) * P(payment|close) * P(fulfilment|payment)
      * LTV * margin * capacity * recency * confidence * time_discount
      - acquisition_cost - fulfilment_cost - risk_cost
    """
    data = dict(inputs or {})
    missing = _missing(data, ERV_REQUIRED)
    if missing:
        return {
            "schema_version": "empire.predictive_revenue.erv.v1",
            "status": "UNAVAILABLE",
            "missing_fields": missing,
            "reason": "insufficient_economic_evidence",
            "unknown_is_zero": False,
            "prediction_only": True,
            "actual_revenue": False,
            "execution_authority": "none",
        }

    probabilities = {
        name: _probability(data[name], name)
        for name in (
            "probability_close",
            "probability_payment_given_close",
            "probability_fulfilment_given_payment",
        )
    }
    modifiers = {
        name: _probability(data[name], name)
        for name in (
            "margin_factor",
            "capacity_factor",
            "recency_factor",
            "confidence",
            "time_discount_factor",
        )
    }
    ltv_cents = _number(data["ltv_cents"], "ltv_cents")
    acquisition_cost = _number(
        data["acquisition_cost_cents"],
        "acquisition_cost_cents",
    )
    fulfilment_cost = _number(
        data["fulfilment_cost_cents"],
        "fulfilment_cost_cents",
    )
    risk_cost = _number(data["risk_cost_cents"], "risk_cost_cents")
    if min(
        ltv_cents,
        acquisition_cost,
        fulfilment_cost,
        risk_cost,
    ) < 0:
        raise ValueError("ERV monetary inputs must be nonnegative")

    probability_chain = prod(probabilities.values())
    modifier_chain = prod(modifiers.values())
    gross_expected_value = (
        probability_chain * ltv_cents * modifier_chain
    )
    total_cost = acquisition_cost + fulfilment_cost + risk_cost
    erv = gross_expected_value - total_cost

    return {
        "schema_version": "empire.predictive_revenue.erv.v1",
        "status": "AVAILABLE",
        "formula": (
            "P_CLOSE*P_PAYMENT_GIVEN_CLOSE*P_FULFIL_GIVEN_PAYMENT*"
            "LTV*MARGIN*CAPACITY*RECENCY*CONFIDENCE*TIME_DISCOUNT"
            "-CAC-FULFILMENT_COST-RISK_COST"
        ),
        "probabilities": probabilities,
        "modifiers": modifiers,
        "probability_chain": round(probability_chain, 12),
        "modifier_chain": round(modifier_chain, 12),
        "ltv_cents": ltv_cents,
        "gross_expected_value_cents": round(gross_expected_value, 4),
        "total_cost_cents": round(total_cost, 4),
        "expected_revenue_value_cents": round(erv, 4),
        "positive_expected_value": erv > 0,
        "unknown_is_zero": False,
        "prediction_only": True,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def revenue_state_snapshot(
    state: str,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate one revenue-truth state against its minimum evidence."""
    normalized = str(state or "").strip().lower()
    if normalized not in REVENUE_STATES:
        raise ValueError(
            "state must be one of: " + ", ".join(REVENUE_STATES)
        )
    evidence_map = dict(evidence or {})
    required = STATE_EVIDENCE[normalized]
    missing = [
        field for field in required
        if not str(evidence_map.get(field) or "").strip()
    ]
    verified = not missing

    return {
        "schema_version": "empire.predictive_revenue.state.v1",
        "state": normalized,
        "state_index": REVENUE_STATES.index(normalized),
        "evidence_complete": verified,
        "required_evidence_fields": list(required),
        "missing_evidence_fields": missing,
        "predicted_is_verified": False,
        "settled_is_revenue_recognized": (
            normalized == "revenue_recognized"
        ),
        "actual_revenue": (
            normalized in {"revenue_recognized", "fulfilled", "retained"}
            and verified
        ),
        "execution_authority": "none",
    }


def next_best_action_value(
    actions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Rank actions by expected incremental revenue, not generic score."""
    rows: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []
    required = (
        "action_key",
        "probability_action_changes_outcome",
        "incremental_revenue_if_changed_cents",
        "action_cost_cents",
        "confidence",
    )

    for raw in actions:
        data = dict(raw or {})
        missing = _missing(data, required)
        action_key = str(data.get("action_key") or "").strip()
        if not action_key:
            missing = list(dict.fromkeys(["action_key", *missing]))
        if missing:
            unavailable.append({
                "action_key": action_key or None,
                "status": "UNAVAILABLE",
                "missing_fields": missing,
            })
            continue

        change_probability = _probability(
            data["probability_action_changes_outcome"],
            "probability_action_changes_outcome",
        )
        confidence = _probability(data["confidence"], "confidence")
        incremental = _number(
            data["incremental_revenue_if_changed_cents"],
            "incremental_revenue_if_changed_cents",
        )
        cost = _number(data["action_cost_cents"], "action_cost_cents")
        if incremental < 0 or cost < 0:
            raise ValueError("action revenue and cost must be nonnegative")

        gross = change_probability * incremental * confidence
        net = gross - cost
        rows.append({
            "action_key": action_key,
            "status": "AVAILABLE",
            "expected_incremental_revenue_cents": round(gross, 4),
            "action_cost_cents": cost,
            "expected_incremental_value_cents": round(net, 4),
            "recommendation_only": True,
            "execution_authority": "none",
        })

    rows.sort(
        key=lambda row: (
            row["expected_incremental_value_cents"],
            row["action_key"],
        ),
        reverse=True,
    )
    for rank, row in enumerate(rows, 1):
        row["rank"] = rank

    return {
        "schema_version": "empire.predictive_revenue.nba.v1",
        "status": "AVAILABLE" if rows else "UNAVAILABLE",
        "available_action_count": len(rows),
        "unavailable_action_count": len(unavailable),
        "recommended_action": rows[0] if rows else None,
        "actions": rows,
        "unavailable_actions": unavailable,
        "optimization_target": "expected_incremental_revenue",
        "recommendation_only": True,
        "execution_authority": "none",
    }


def revenue_formula_identification_bounds(
    inputs: Mapping[str, Any],
) -> dict[str, Any]:
    """Mathematical range with *unknown* funnel probabilities in [0,1].

    This is a partial-identification bound, not a point forecast,
    Bayesian posterior, statistical confidence interval or buyer revenue.
    """
    data = dict(inputs or {})
    missing = [name for name in CORE_FACTORS if data.get(name) is None]
    if data.get("ltv_cents") is None:
        return {
            "schema_version": "empire.predictive_revenue.bounds.v1",
            "status": "UNAVAILABLE",
            "reason": "ltv_unknown",
            "missing_fields": [*missing, "ltv_cents"],
            "lower_bound_cents": None,
            "upper_bound_cents": None,
            "unknown_is_zero": False,
            "prediction_only": True,
            "actual_revenue": False,
            "execution_authority": "none",
        }
    ltv = _number(data["ltv_cents"], "ltv_cents")
    if ltv < 0:
        raise ValueError("ltv_cents must be nonnegative")
    known = {name: _probability(data[name], name)
             for name in CORE_FACTORS if name not in missing}
    upper = prod(known.values()) * ltv
    lower = 0.0 if missing else upper
    if not all(isfinite(v) for v in (upper, lower)):
        raise ValueError("formula bounds must be finite")
    return {
        "schema_version": "empire.predictive_revenue.bounds.v1",
        "status": "PARTIALLY_IDENTIFIED" if missing else "FULLY_SPECIFIED_SCENARIO",
        "missing_fields": missing,
        "known_factor_count": len(known),
        "lower_bound_cents": round(lower, 4),
        "upper_bound_cents": round(upper, 4),
        "assumed_unknown_factor_range": [0, 1] if missing else None,
        "interval_type": "deterministic_hypothetical_bounds_not_statistical_confidence",
        "source_data_verified": False,
        "unknown_is_zero": False,
        "prediction_only": True,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def review_revenue_factor_counterfactuals(
    inputs: Mapping[str, Any],
    interventions: Sequence[Mapping[str, Any]],
    *,
    factor_evidence_refs: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, Any]:
    """Use the *existing* ten-factor formula to model one change at a time.

    Delta = LTV * (target - baseline) * product(other factors).
    The arithmetic is exact for the canonical multiplicative model. A proposed
    target is a hypothesis, NOT a calibrated causal effect or expected ROI.
    Every baseline factor and LTV must carry its own source provenance; if any
    are missing there is no numeric intervention ranking.
    """
    schema = "empire.predictive_revenue.factor_counterfactuals.v1"
    data = dict(inputs or {})
    bounds = revenue_formula_identification_bounds(data)
    refs = dict(factor_evidence_refs or {})
    required = (*CORE_FACTORS, "ltv_cents")
    unproven = [
        key for key in required
        if not isinstance(refs.get(key), (list, tuple))
        or not refs[key]
        or len(refs[key]) > 12
        or any(not isinstance(value, str)
               or not value.strip() or len(value) > 240
               for value in refs[key])
    ]
    missing = [key for key in required if data.get(key) is None]
    if len(interventions) > 40:
        raise ValueError("intervention scenario limit exceeded")
    if missing or unproven:
        return {
            "schema_version": schema,
            "status": "EVIDENCE_HOLD",
            "reason": "complete_evidenced_baseline_required",
            "missing_factor_inputs": missing,
            "missing_factor_evidence_refs": unproven,
            "identification_bounds": bounds,
            "scenarios": [],
            "hypothetical_not_causal": True,
            "actual_revenue": False,
            "execution_authority": "none",
        }
    base = predictive_revenue_formula(data)
    if base["status"] != "AVAILABLE":
        raise ValueError("baseline funnel unavailable")
    baseline = base["predicted_revenue_cents"]
    scenarios: list[dict[str, Any]] = []
    seen: set[str] = set()
    for proposed in interventions:
        if not isinstance(proposed, Mapping):
            raise ValueError("counterfactual must be an object")
        action = proposed.get("action_key")
        factor = proposed.get("factor")
        if (not isinstance(action, str) or not action.strip()
                or len(action) > 120 or action in seen):
            raise ValueError("unique bounded action_key required")
        seen.add(action)
        if factor not in CORE_FACTORS:
            raise ValueError("unknown funnel factor")
        target = _probability(proposed.get("target_value"), "target_value")
        current = _probability(data[factor], factor)
        if target < current:
            raise ValueError("improvement scenario cannot lower a factor")
        cost = _number(proposed.get("scenario_cost_cents"), "scenario_cost_cents")
        if cost < 0:
            raise ValueError("scenario cost must be nonnegative")
        changed = dict(data)
        changed[factor] = target
        scenario = predictive_revenue_formula(changed)
        hypothetical_delta = scenario["predicted_revenue_cents"] - baseline
        # Use the unrounded symbolic derivative for the revenue sensitivity.
        slope = _number(data["ltv_cents"], "ltv_cents") * prod(
            _probability(data[other], other)
            for other in CORE_FACTORS if other != factor
        )
        net = hypothetical_delta - cost
        if not all(isfinite(v) for v in (hypothetical_delta, slope, net)):
            raise ValueError("counterfactual overflow")
        scenarios.append({
            "action_key": action,
            "factor": factor,
            "baseline_factor": current,
            "hypothetical_target_factor": target,
            "marginal_sensitivity_cents_per_unit": round(slope, 4),
            "hypothetical_incremental_revenue_cents": round(hypothetical_delta, 4),
            "hypothetical_net_change_cents": round(net, 4),
            "scenario_cost_cents": cost,
            "baseline_evidence_refs": list(dict.fromkeys(refs[factor])),
            "target_is_evidenced": False,
            "scenario_only": True,
            "causal_effect_established": False,
            "commercial_execution_authorized": False,
        })
    scenarios.sort(key=lambda row: (
        -row["hypothetical_net_change_cents"], row["action_key"],
    ))
    return {
        "schema_version": schema,
        "status": "HYPOTHETICAL_REVIEW" if scenarios else "NO_SCENARIOS",
        "baseline_formula_status": base["status"],
        "baseline_predicted_revenue_cents": baseline,
        "scenarios": scenarios,
        "scenario_count": len(scenarios),
        "formula": "LTV*(TARGET-BASELINE)*PRODUCT(OTHER_FUNNEL_FACTORS)",
        "scenario_values_are_not_causal_estimates": True,
        "scenario_values_are_not_expected_incremental_profit": True,
        "independence_and_calibration_not_proven": True,
        "measurement_required_before_action_optimization": True,
        "unknown_is_zero": False,
        "prediction_only": True,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def review_joint_revenue_counterfactual(
    inputs: Mapping[str, Any],
    factor_targets: Mapping[str, Any],
    *,
    scenario_cost_cents: Any,
    factor_evidence_refs: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, Any]:
    """Exact multiplicative multi-factor what-if with Shapley decomposition.

    Unlike adding independent one-factor gains, this includes the interaction
    of jointly changed factors. Shapley contributions share the mathematical
    joint scenario uplift; they are NOT causal, measured, or contractual.
    """
    schema = "empire.predictive_revenue.joint_counterfactual.v1"
    baseline = review_revenue_factor_counterfactuals(
        inputs, [], factor_evidence_refs=factor_evidence_refs,
    )
    if baseline["status"] == "EVIDENCE_HOLD":
        return {
            "schema_version": schema,
            "status": "EVIDENCE_HOLD",
            "reason": "canonical_baseline_or_provenance_incomplete",
            "missing_factor_inputs": baseline["missing_factor_inputs"],
            "missing_factor_evidence_refs": baseline["missing_factor_evidence_refs"],
            "identification_bounds": baseline["identification_bounds"],
            "joint_delta_cents": None,
            "causal_attribution_claimed": False,
            "execution_authority": "none",
        }
    if not isinstance(factor_targets, Mapping) or not 1 <= len(factor_targets) <= len(CORE_FACTORS):
        raise ValueError("joint scenario requires 1 to 10 existing funnel factors")
    cost = _number(scenario_cost_cents, "scenario_cost_cents")
    if cost < 0:
        raise ValueError("scenario cost must be nonnegative")
    values = dict(inputs)
    factors = tuple(sorted(factor_targets))
    for factor in factors:
        if factor not in CORE_FACTORS:
            raise ValueError("unknown joint funnel factor")
        start = _probability(inputs[factor], factor)
        target = _probability(factor_targets[factor], f"{factor}_target")
        if target < start:
            raise ValueError("joint improvement cannot lower a factor")
        values[factor] = target
    full = predictive_revenue_formula(values)
    base = predictive_revenue_formula(inputs)
    # Calculate on the original (unrounded) canonical product to avoid a
    # rounding-dependent Shapley residual.
    ltv = _number(inputs["ltv_cents"], "ltv_cents")

    def value(changed: frozenset[str]) -> float:
        result = ltv * prod(
            _probability(
                factor_targets[factor] if factor in changed else inputs[factor],
                factor,
            ) for factor in CORE_FACTORS
        )
        if not isfinite(result):
            raise ValueError("joint counterfactual overflow")
        return result

    all_factors = frozenset(factors)
    total_delta = value(all_factors) - value(frozenset())
    isolated = {
        factor: value(frozenset({factor})) - value(frozenset())
        for factor in factors
    }
    n = len(factors)
    attribution: list[dict[str, Any]] = []
    for factor in factors:
        others = tuple(key for key in factors if key != factor)
        contribution = 0.0
        for size in range(n):
            for subset in combinations(others, size):
                fixed = frozenset(subset)
                weight = factorial(size) * factorial(n - size - 1) / factorial(n)
                contribution += weight * (
                    value(fixed | {factor}) - value(fixed)
                )
        attribution.append({
            "factor": factor,
            "baseline_factor": _probability(inputs[factor], factor),
            "hypothetical_target_factor": values[factor],
            "shapley_mathematical_share_cents": round(contribution, 4),
            "isolated_factor_delta_cents": round(isolated[factor], 4),
            "baseline_evidence_refs": list(dict.fromkeys(factor_evidence_refs[factor])),
            "causal_attribution_claimed": False,
        })
    if abs(sum(item["shapley_mathematical_share_cents"] for item in attribution)
           - round(total_delta, 4)) > 0.001:
        raise ValueError("joint counterfactual attribution mismatch")
    synergy = total_delta - sum(isolated.values())
    return {
        "schema_version": schema,
        "status": "HYPOTHETICAL_REVIEW",
        "formula": "JOINT_PRODUCT_OF_TARGET_FACTORS_MINUS_BASELINE_PRODUCT",
        "baseline_predicted_revenue_cents": base["predicted_revenue_cents"],
        "hypothetical_joint_predicted_revenue_cents": full["predicted_revenue_cents"],
        "joint_delta_cents": round(total_delta, 4),
        "isolated_increment_sum_cents": round(sum(isolated.values()), 4),
        "multi_factor_interaction_cents": round(synergy, 4),
        "scenario_cost_cents": cost,
        "hypothetical_net_delta_cents": round(total_delta - cost, 4),
        "attribution_method": "exact_shapley_over_scenario_factor_subsets",
        "mathematical_factor_attributions": attribution,
        "attributions_not_causal_or_observed": True,
        "scenario_values_not_expected_profit": True,
        "calibration_and_independence_not_established": True,
        "execution_authority": "none",
        "payment_authorized": False,
        "outbound_authorized": False,
        "model_weight_mutation": False,
        "prediction_only": True,
        "actual_revenue": False,
    }
