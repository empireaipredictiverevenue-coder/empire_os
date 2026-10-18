"""Enhanced Predictive Cloud Formula for EmpireOS.

Predictive Revenue estimates opportunity-level commercial value.
Predictive Cloud evaluates whether the wider intelligence/decision system is
trustworthy enough for those values to matter at portfolio level.

Cloud-adjusted portfolio value =
    sum(available ERV)
    * geometric_mean(cloud trust factors)
    * (1 - residual_uncertainty)

Missing evidence remains UNKNOWN, never zero. A genuinely observed zero factor
can collapse the trust multiplier; an unknown factor makes the formula
UNAVAILABLE. This module is read-only decision support and grants no execution,
commercial, payment, accounting or model-mutation authority.
"""
from __future__ import annotations

from math import isfinite, prod
from typing import Any, Mapping, Sequence


CLOUD_FACTORS = (
    "intelligence_quality",
    "evidence_coverage",
    "signal_freshness",
    "calibration_confidence",
    "causal_confidence",
    "runtime_reliability",
    "governance_readiness",
    "learning_readiness",
    "portfolio_fit",
    "scalability_readiness",
)

CONSTRAINT_KEYS = (
    "capacity",
    "compliance",
    "inventory",
    "cash",
    "authority",
    "fulfilment",
)


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


def _portfolio_erv(
    opportunities: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    available: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []

    for raw in opportunities:
        row = dict(raw or {})
        key = str(
            row.get("opportunity_key")
            or row.get("candidate_id")
            or row.get("id")
            or ""
        ).strip()
        value = row.get("expected_revenue_value_cents")
        status = str(row.get("status") or "").upper()

        if value is None or status != "AVAILABLE":
            unavailable.append({
                "opportunity_key": key or None,
                "reason": (
                    row.get("reason")
                    or "expected_revenue_value_unavailable"
                ),
                "missing_fields": list(
                    row.get("missing_fields") or []
                ),
            })
            continue

        numeric = _number(
            value,
            f"expected_revenue_value_cents:{key or 'unknown'}",
        )
        available.append({
            "opportunity_key": key or None,
            "expected_revenue_value_cents": numeric,
        })

    return {
        "available": available,
        "unavailable": unavailable,
        "total_opportunity_count": len(available) + len(unavailable),
        "portfolio_value_scope": "AVAILABLE_ONLY",
        "complete_portfolio_value_known": bool(available) and not unavailable,
        "unknown_opportunities_included_as_zero": False,
        "portfolio_expected_revenue_value_cents": round(
            sum(
                row["expected_revenue_value_cents"]
                for row in available
            ),
            4,
        ),
    }


def _constraint_review(
    constraints: Mapping[str, Any] | None,
) -> dict[str, Any]:
    data = dict(constraints or {})
    states: dict[str, bool | None] = {}
    blockers: list[str] = []
    unknown: list[str] = []

    for key in CONSTRAINT_KEYS:
        value = data.get(key)
        if value is None:
            states[key] = None
            unknown.append(key)
            continue
        if not isinstance(value, bool):
            raise ValueError(f"constraint:{key} must be boolean or null")
        states[key] = value
        if value is False:
            blockers.append(key)

    if blockers:
        state = "BLOCKED"
    elif unknown:
        state = "UNKNOWN"
    else:
        state = "CLEAR"

    return {
        "state": state,
        "constraints": states,
        "blockers": blockers,
        "unknown_constraints": unknown,
        "execution_authority": "none",
    }


def predictive_cloud_formula(
    *,
    factors: Mapping[str, Any],
    residual_uncertainty: Any,
    opportunities: Sequence[Mapping[str, Any]],
    constraints: Mapping[str, Any] | None = None,
    trend_intelligence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate the enhanced Predictive Cloud formula.

    PCV =
      PortfolioERV
      * GM(IQ, EC, SF, CC, CAUSAL, RR, GR, LR, PF, SR)
      * (1-U)

    The geometric mean is deliberate: it rewards balanced system quality and
    prevents one strong subsystem from hiding a genuinely weak one.
    """
    data = dict(factors or {})
    missing = [
        name for name in CLOUD_FACTORS
        if data.get(name) is None
    ]
    if residual_uncertainty is None:
        missing.append("residual_uncertainty")

    portfolio = _portfolio_erv(opportunities)
    constraint_review = _constraint_review(constraints)
    trend = dict(trend_intelligence or {})
    trend_available = (
        str(trend.get("status") or "").upper() == "AVAILABLE"
        and str(
            trend.get("future_opportunity_status") or ""
        ).upper() == "AVAILABLE"
        and trend.get("trend_confidence") is not None
        and trend.get("trend_opportunity_alignment") is not None
    )
    trend_context = {
        "available": trend_available,
        "algorithm": "empire.future_trend.v1",
        "direction": trend.get("direction"),
        "velocity_per_day": trend.get("velocity_per_day"),
        "acceleration_per_day": trend.get("acceleration_per_day"),
        "persistence": trend.get("persistence"),
        "trend_confidence": trend.get("trend_confidence"),
        "trend_opportunity_alignment": trend.get(
            "trend_opportunity_alignment"
        ),
        "evidence_refs": list(trend.get("evidence_refs") or []),
        "forecast_context_only": True,
        "causal_claim": False,
    }

    if missing:
        return {
            "schema_version": "empire.predictive_cloud.formula.v1",
            "status": "UNAVAILABLE",
            "missing_fields": missing,
            "reason": "unknown_cloud_inputs_preserved",
            "portfolio": portfolio,
            "constraints": constraint_review,
            "future_trend_context": trend_context,
            "unknown_is_zero": False,
            "prediction_only": True,
            "actual_revenue": False,
            "model_weight_mutation": False,
            "execution_authority": "none",
        }

    bounded = {
        name: _probability(data[name], name)
        for name in CLOUD_FACTORS
    }
    uncertainty = _probability(
        residual_uncertainty,
        "residual_uncertainty",
    )
    trust_product = prod(bounded.values())
    trust_multiplier = trust_product ** (1.0 / len(bounded))
    uncertainty_retention = 1.0 - uncertainty

    portfolio_erv = float(
        portfolio["portfolio_expected_revenue_value_cents"]
    )
    cloud_adjusted_value = (
        portfolio_erv
        * trust_multiplier
        * uncertainty_retention
    )
    cloud_operating_score = (
        100.0 * trust_multiplier * uncertainty_retention
    )

    weakest = min(
        bounded.items(),
        key=lambda item: (item[1], item[0]),
    )

    forward_outlook = {
        "status": "UNAVAILABLE",
        "reason": "future_trend_context_unavailable",
        "cloud_forward_score": None,
        "trend_confidence": trend_context["trend_confidence"],
        "trend_opportunity_alignment": trend_context[
            "trend_opportunity_alignment"
        ],
        "prediction_only": True,
    }
    if trend_available:
        trend_confidence = _probability(
            trend_context["trend_confidence"],
            "trend_confidence",
        )
        alignment = _probability(
            trend_context["trend_opportunity_alignment"],
            "trend_opportunity_alignment",
        )
        forward_factor = (
            (cloud_operating_score / 100.0)
            * trend_confidence
            * alignment
        ) ** (1.0 / 3.0)
        forward_outlook = {
            "status": "AVAILABLE",
            "cloud_forward_score": round(
                100.0 * forward_factor,
                4,
            ),
            "trend_confidence": trend_confidence,
            "trend_opportunity_alignment": alignment,
            "prediction_only": True,
            "causal_claim": False,
        }

    return {
        "schema_version": "empire.predictive_cloud.formula.v1",
        "status": "AVAILABLE",
        "formula": (
            "SUM(ERV)*GEOMETRIC_MEAN("
            "INTELLIGENCE_QUALITY,EVIDENCE_COVERAGE,SIGNAL_FRESHNESS,"
            "CALIBRATION_CONFIDENCE,CAUSAL_CONFIDENCE,"
            "RUNTIME_RELIABILITY,GOVERNANCE_READINESS,"
            "LEARNING_READINESS,PORTFOLIO_FIT,SCALABILITY_READINESS"
            ")*(1-RESIDUAL_UNCERTAINTY)"
        ),
        "factors": bounded,
        "residual_uncertainty": uncertainty,
        "uncertainty_retention": round(
            uncertainty_retention,
            12,
        ),
        "trust_multiplier": round(trust_multiplier, 12),
        "cloud_operating_score": round(cloud_operating_score, 4),
        "portfolio": portfolio,
        "cloud_adjusted_portfolio_value_cents": round(
            cloud_adjusted_value,
            4,
        ),
        # Preserve legacy available-only value, but never represent a
        # truncated/partially unknown portfolio as its complete value.
        "cloud_adjusted_portfolio_value_is_partial": (
            not portfolio["complete_portfolio_value_known"]
        ),
        "cloud_adjusted_full_portfolio_value_cents": (
            round(cloud_adjusted_value, 4)
            if portfolio["complete_portfolio_value_known"] else None
        ),
        "weakest_cloud_factor": {
            "name": weakest[0],
            "value": weakest[1],
        },
        "constraints": constraint_review,
        "future_trend_context": trend_context,
        "forward_outlook": forward_outlook,
        "constraint_clear_for_review": (
            constraint_review["state"] == "CLEAR"
        ),
        "predicted_revenue_is_verified_revenue": False,
        "unknown_is_zero": False,
        "prediction_only": True,
        "actual_revenue": False,
        "model_weight_mutation": False,
        "capital_execution": False,
        "commercial_authority": "none",
        "execution_authority": "none",
    }


def compare_cloud_snapshots(
    previous: Mapping[str, Any],
    current: Mapping[str, Any],
) -> dict[str, Any]:
    """Describe score/value deltas without claiming causality."""
    prev = dict(previous or {})
    curr = dict(current or {})
    fields = (
        "cloud_operating_score",
        "cloud_adjusted_portfolio_value_cents",
        "trust_multiplier",
        "residual_uncertainty",
    )
    missing = [
        field for field in fields
        if prev.get(field) is None or curr.get(field) is None
    ]
    if missing:
        return {
            "schema_version": "empire.predictive_cloud.delta.v1",
            "status": "UNAVAILABLE",
            "missing_fields": missing,
            "causal_claim": False,
            "execution_authority": "none",
        }

    deltas = {
        field: round(
            _number(curr[field], f"current:{field}")
            - _number(prev[field], f"previous:{field}"),
            6,
        )
        for field in fields
    }
    return {
        "schema_version": "empire.predictive_cloud.delta.v1",
        "status": "AVAILABLE",
        "deltas": deltas,
        "improvement_claim": "descriptive_only",
        "causal_claim": False,
        "execution_authority": "none",
    }


def review_cloud_quality_counterfactuals(
    *,
    factors: Mapping[str, Any],
    residual_uncertainty: Any,
    opportunities: Sequence[Mapping[str, Any]],
    constraints: Mapping[str, Any] | None,
    improvements: Sequence[Mapping[str, Any]],
    evidence_refs: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, Any]:
    """Quantify hypothetical trust/uncertainty improvements using Cloud v1.

    No new model or coefficients. The geometric-mean formula is recomputed for
    each one-factor proposal; predicted portfolio value is only reported when
    *every* included opportunity has a known ERV and at least one is present.
    """
    schema = "empire.predictive_cloud.quality_counterfactuals.v1"
    if len(improvements) > 40:
        raise ValueError("cloud scenario limit exceeded")
    refs = dict(evidence_refs or {})
    required = (*CLOUD_FACTORS, "residual_uncertainty")
    absent = [
        field for field in required
        if field != "residual_uncertainty" and factors.get(field) is None
        or field == "residual_uncertainty" and residual_uncertainty is None
    ]
    unproven = [
        field for field in required
        if not isinstance(refs.get(field), (list, tuple))
        or not refs[field] or len(refs[field]) > 12
        or any(not isinstance(ref, str) or not ref.strip() or len(ref) > 240
               for ref in refs[field])
    ]
    if absent or unproven:
        return {
            "schema_version": schema,
            "status": "EVIDENCE_HOLD",
            "missing_inputs": absent,
            "missing_evidence_refs": unproven,
            "hypothetical_scenarios": [],
            "prediction_only": True,
            "actual_revenue": False,
            "execution_authority": "none",
        }
    baseline = predictive_cloud_formula(
        factors=factors,
        residual_uncertainty=residual_uncertainty,
        opportunities=opportunities,
        constraints=constraints,
    )
    if baseline["status"] != "AVAILABLE":
        return {
            "schema_version": schema,
            "status": "EVIDENCE_HOLD",
            "reason": "canonical_cloud_formula_unavailable",
            "hypothetical_scenarios": [],
            "execution_authority": "none",
        }

    scenarios: list[dict[str, Any]] = []
    names: set[str] = set()
    for row in improvements:
        if not isinstance(row, Mapping):
            raise ValueError("improvement must be a mapping")
        action = row.get("action_key")
        factor = row.get("factor")
        if (not isinstance(action, str) or not action.strip()
                or len(action) > 120 or action in names):
            raise ValueError("unique bounded action_key required")
        names.add(action)
        if factor not in (*CLOUD_FACTORS, "residual_uncertainty"):
            raise ValueError("unknown cloud factor")
        target = _probability(row.get("target_value"), "target_value")
        current = _probability(
            residual_uncertainty if factor == "residual_uncertainty"
            else factors[factor], str(factor),
        )
        if ((target > current) if factor == "residual_uncertainty"
                else (target < current)):
            raise ValueError("cloud scenario must improve selected factor")
        factors_new = dict(factors)
        uncertainty_new = residual_uncertainty
        if factor == "residual_uncertainty":
            uncertainty_new = target
        else:
            factors_new[str(factor)] = target
        new = predictive_cloud_formula(
            factors=factors_new,
            residual_uncertainty=uncertainty_new,
            opportunities=opportunities,
            constraints=constraints,
        )
        delta_score = new["cloud_operating_score"] - baseline["cloud_operating_score"]
        initial_value = baseline["cloud_adjusted_full_portfolio_value_cents"]
        new_value = new["cloud_adjusted_full_portfolio_value_cents"]
        value_change = (
            round(new_value - initial_value, 4)
            if initial_value is not None and new_value is not None else None
        )
        scenarios.append({
            "action_key": action,
            "factor": factor,
            "baseline_factor": current,
            "hypothetical_target_factor": target,
            "hypothetical_cloud_score_change": round(delta_score, 4),
            "hypothetical_complete_portfolio_value_change_cents": value_change,
            "baseline_factor_evidence_refs": list(dict.fromkeys(refs[factor])),
            "target_has_observed_causal_evidence": False,
            "model_calibration_not_established_by_this_review": True,
            "action_authorized": False,
        })
    scenarios.sort(key=lambda row: (
        -row["hypothetical_cloud_score_change"], row["action_key"],
    ))
    return {
        "schema_version": schema,
        "status": "HYPOTHETICAL_REVIEW" if scenarios else "NO_SCENARIOS",
        "baseline_cloud_operating_score": baseline["cloud_operating_score"],
        "baseline_cloud_adjusted_full_portfolio_value_cents": baseline[
            "cloud_adjusted_full_portfolio_value_cents"
        ],
        "portfolio_scope": baseline["portfolio"]["portfolio_value_scope"],
        "portfolio_complete": baseline["portfolio"]["complete_portfolio_value_known"],
        "operating_constraints": baseline["constraints"],
        "hypothetical_scenarios": scenarios,
        "monetary_deltas_are_not_realized_profit": True,
        "improvements_have_no_causal_proof": True,
        "forecast_and_outcomes_separate": True,
        "prediction_only": True,
        "actual_revenue": False,
        "commercial_authority": "none",
        "execution_authority": "none",
    }
