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

from math import prod
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
)


def _number(value: Any, name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc


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
