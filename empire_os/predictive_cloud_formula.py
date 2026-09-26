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

from math import prod
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
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc


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

        if value is None or status == "UNAVAILABLE":
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

    if missing:
        return {
            "schema_version": "empire.predictive_cloud.formula.v1",
            "status": "UNAVAILABLE",
            "missing_fields": missing,
            "reason": "unknown_cloud_inputs_preserved",
            "portfolio": portfolio,
            "constraints": constraint_review,
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
        "weakest_cloud_factor": {
            "name": weakest[0],
            "value": weakest[1],
        },
        "constraints": constraint_review,
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
