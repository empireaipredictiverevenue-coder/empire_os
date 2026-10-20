"""Tenant/product-specific conversion forecasting science, with causal time order.

Read-only evaluation of existing original-calibration *candidates*. A supplied
packet is NOT an authenticated registry readback, even if syntactically valid.
No customer-facing model or financial promotion can result from this evaluator.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from math import sqrt
from typing import Any

from empire_os.outcome_feedback import validate_verified_feedback
from empire_os.predictive_calibration import review_commercial_prediction

SCHEMA = "empire.predictive_revenue.product_scientific_holdout.v1"
MIN_HISTORY = 20
MIN_EVALUATIONS = 12
MAX_RECORDS = 500
MAX_TEXT = 160
ONE = Decimal(1)
FOUR = Decimal("0.000001")


class ProductScienceHold(ValueError):
    """Fail closed on mismatched source, tenant, time or cohort semantics."""


def _text(value: Any, key: str) -> str:
    if (type(value) is not str or not value or value.strip() != value
            or len(value) > MAX_TEXT or any(ord(ch) < 32 for ch in value)):
        raise ProductScienceHold(f"{key} missing or malformed")
    return value


def _when(value: Any, key: str) -> datetime:
    if type(value) is not str:
        raise ProductScienceHold(f"{key} requires original timezone-aware timestamp")
    try:
        out = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ProductScienceHold(f"{key} invalid") from None
    if out.tzinfo is None or out.utcoffset() is None:
        raise ProductScienceHold(f"{key} missing timezone")
    return out.astimezone(timezone.utc)


def _num(value: Any, key: str) -> Decimal:
    if type(value) not in (float, int):
        raise ProductScienceHold(f"{key} invalid numeric type")
    try:
        out = Decimal(str(value))
    except Exception:
        raise ProductScienceHold(f"{key} invalid numeric value") from None
    if not out.is_finite() or not 0 <= out <= 1:
        raise ProductScienceHold(f"{key} outside probability range")
    return out


def _round(x: Decimal) -> float:
    return float(x.quantize(FOUR, rounding=ROUND_HALF_UP))


def _wilson(success: int, total: int) -> tuple[float, float]:
    # A marginal interval for observed frequency, not a predictive interval
    # for individual commercial opportunities.
    z = 1.959963984540054
    p = success / total
    z2 = z * z
    denominator = 1 + z2 / total
    center = (p + z2 / (2 * total)) / denominator
    spread = z * sqrt(p * (1 - p) / total + z2 / (4 * total * total))
    return (round(max(0, (center - spread) / denominator), 6),
            round(min(1, (center + spread) / denominator), 6))


def _held(reason: str, *, code: str, sample_count: int) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "status": "PRODUCT_HOLDOUT_INSUFFICIENT_ORIGINAL_EVIDENCE",
        "product_code": code,
        "submitted_calibration_count": sample_count,
        "historical_baseline_period_count": None,
        "out_of_sample_evaluation_count": 0,
        "model_brier": None, "historical_baseline_brier": None,
        "skill_vs_past_only_baseline": None, "calibration_gap": None,
        "observed_rate_wilson_95": None, "reason_code": reason,
        "original_registry_readback_authenticated": False,
        "original_source_issuer_authenticated": False,
        "forecast_eligible_for_customer": False,
        "economic_memory_update_eligible": False,
        "model_weight_mutation": False,
        "realized_revenue_verified_by_this_review": False,
        "production_activated": False, "execution_authority": "none",
    }


def evaluate_product_scientific_holdout(
    *, tenant_id: str, product_code: str,
    calibration_packets: Sequence[Mapping[str, Any]],
    catalog: Mapping[str, Any], as_of: datetime,
) -> dict[str, Any]:
    """Strict prospective baseline scored only from outcomes already available.

    Source owner must separately authenticate both the immutable BEFORE-outcome
    forecast registration and AFTER-outcome independent ledger. This pure
    evaluator cannot do that; even favorable statistics are lab-only.
    """
    tenant = _text(tenant_id, "tenant_id")
    code = _text(product_code, "product_code")
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ProductScienceHold("trusted evaluation timestamp required")
    now = as_of.astimezone(timezone.utc)
    if (not isinstance(catalog, Mapping)
            or type(catalog.get("products")) is not list
            or len(catalog["products"]) > MAX_RECORDS):
        raise ProductScienceHold("verified catalogue product binding required")
    candidate_products: dict[str, str] = {}
    for row in catalog["products"]:
        if not isinstance(row, Mapping):
            raise ProductScienceHold("untrusted catalogue row")
        pid = row.get("product_id")
        sku = row.get("product_code")
        if (row.get("catalog_state") != "VERIFIED"
                or row.get("version_state") != "VERIFIED"
                or not isinstance(pid, str) or not pid or not isinstance(sku, str) or not sku):
            continue
        if pid in candidate_products:
            raise ProductScienceHold("duplicate original product identity")
        candidate_products[pid] = sku
    if code not in candidate_products.values():
        return _held("CANONICAL_PRODUCT_VERSION_NOT_EVIDENCED", code=code, sample_count=0)
    if (type(calibration_packets) not in (list, tuple)
            or len(calibration_packets) > MAX_RECORDS):
        raise ProductScienceHold("calibration cohort must be bounded ordered collection")
    if len(calibration_packets) < MIN_HISTORY + MIN_EVALUATIONS:
        return _held("INSUFFICIENT_TIME_ORDERED_CALIBRATION_PACKETS",
                     code=code, sample_count=len(calibration_packets))

    unique_predictions: set[str] = set()
    unique_outcomes: set[str] = set()
    unique_orders: set[str] = set()
    # NO packet output (names, tenant identifier, refs, revenue) is exported.
    records: list[tuple[datetime, datetime, Decimal, int]] = []
    for packet in calibration_packets:
        if not isinstance(packet, Mapping):
            raise ProductScienceHold("untrusted calibration packet")
        if (packet.get("schema_version") != "empire.commercial_prediction_calibration.v1"
                or packet.get("calibration_ready") is not True
                or packet.get("shadow_only") is not True
                or packet.get("learning_stage") != "SHADOW_LEARNING"
                or packet.get("model_weight_mutation") is not False
                or packet.get("promoted_learning") is not False
                or packet.get("execution_authority") != "none"
                or packet.get("tenant_id") != tenant):
            raise ProductScienceHold("original forecast calibration contract not satisfied")
        prediction = packet.get("prediction")
        feedback = packet.get("feedback")
        if not isinstance(prediction, Mapping) or not isinstance(feedback, Mapping):
            raise ProductScienceHold("original prediction and feedback required")
        if candidate_products.get(feedback.get("product_id")) != code:
            raise ProductScienceHold("outcome not bound to same verified SKU")
        ref = _text(packet.get("prediction_ref"), "prediction_ref")
        outcome = _text(packet.get("outcome_ref"), "outcome_ref")
        order = _text(feedback.get("fulfilment_order_id"), "fulfilment_order_id")
        if (ref in unique_predictions or outcome in unique_outcomes or order in unique_orders):
            raise ProductScienceHold("duplicate prediction, outcome or fulfilment order")
        unique_predictions.add(ref)
        unique_outcomes.add(outcome)
        unique_orders.add(order)
        try:
            validate_verified_feedback(feedback, tenant_id=tenant, as_of=now)
            inspected = review_commercial_prediction(
                prediction=prediction, feedback=feedback, tenant_id=tenant, as_of=now
            )
        except (TypeError, ValueError, KeyError, OverflowError):
            raise ProductScienceHold("calibration and original feedback mismatch") from None
        probability = _num(packet.get("predicted_value"), "predicted_value")
        if (inspected["prediction_ref"] != ref or inspected["outcome_ref"] != outcome
                or _num(inspected["predicted_value"], "original") != probability
                or packet.get("actual_value") != inspected["actual_value"]
                or packet.get("actual_at") != inspected["actual_at"]):
            raise ProductScienceHold("supplied calibration contradicts recomputed outcome")
        issued = _when(inspected["predicted_at"], "prediction_time")
        available = _when(inspected["actual_at"], "actual_time")
        if available > now or issued >= available:
            raise ProductScienceHold("future or retroactive forecast")
        records.append((issued, available, probability, inspected["actual_value"]))
    # Different packet order is fine: temporal order is derived from original dates.
    records.sort(key=lambda r: (r[0], r[1]))
    model_sum = Decimal(0)
    baseline_sum = Decimal(0)
    predictions_sum = Decimal(0)
    successes = 0
    evaluated = 0
    historical_min = MAX_RECORDS
    for issued, available, forecast, actual in records:
        # Strict causal knowledge: outcome becomes eligible only if AVAILABLE
        # before the NEXT forecast was issued (not merely before scoring).
        history = [r[3] for r in records if r[1] < issued]
        if len(history) < MIN_HISTORY:
            continue
        historical_min = min(historical_min, len(history))
        baseline = Decimal(sum(history) + 1) / Decimal(len(history) + 2)
        outcome = Decimal(actual)
        model_sum += (forecast - outcome) ** 2
        baseline_sum += (baseline - outcome) ** 2
        predictions_sum += forecast
        successes += actual
        evaluated += 1
    if evaluated < MIN_EVALUATIONS:
        return _held("INSUFFICIENT_PRIOR_RESOLVED_OUTCOMES_BEFORE_FORECASTS",
                     code=code, sample_count=len(records))
    model_brier = model_sum / Decimal(evaluated)
    baseline_brier = baseline_sum / Decimal(evaluated)
    gap = abs(predictions_sum / Decimal(evaluated) -
              Decimal(successes) / Decimal(evaluated))
    skill = ((baseline_brier - model_brier) / baseline_brier
             if baseline_brier > 0 else None)
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "status": "SUPPLIED_PACKET_STATISTICS_ONLY_ORIGINAL_REGISTRY_HOLD",
        "product_code": code,
        "submitted_calibration_count": len(records),
        "historical_baseline_period_count": historical_min,
        "out_of_sample_evaluation_count": evaluated,
        "model_brier": _round(model_brier),
        "historical_baseline_brier": _round(baseline_brier),
        "skill_vs_past_only_baseline": _round(skill) if skill is not None else None,
        "skill_positive_observed_on_submitted_cohort":
            (skill > 0 if skill is not None else None),
        "observed_conversion_rate": round(successes / evaluated, 6),
        "mean_predicted_probability": _round(predictions_sum / Decimal(evaluated)),
        "calibration_gap": _round(gap),
        "observed_rate_wilson_95": dict(
            zip(("low", "high"), _wilson(successes, evaluated))
        ),
        "interval_kind": "OBSERVED_FREQUENCY_NOT_INDIVIDUAL_FORECAST_CI",
        "model_production_skill_proven": False,
        "original_registry_readback_authenticated": False,
        "original_source_issuer_authenticated": False,
        "forecast_eligible_for_customer": False,
        "economic_memory_update_eligible": False,
        "model_weight_mutation": False,
        "realized_revenue_verified_by_this_review": False,
        "production_activated": False,
        "execution_authority": "none",
    }
