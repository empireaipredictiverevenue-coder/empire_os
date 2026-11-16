"""Wave 33: evidence-gated Predictive Revenue diagnostic intelligence.

Compose EXISTING validated predictive-intelligence cohort readiness, economic
memory's temporal shadow/Brier evaluation and Predictive Cloud forecast/actual
calibration. Add human-readable error deterioration and freshness flags only.
This module trains nothing, never modifies predictions or commercial truth,
does not infer buyer causality, and does not create another scoring engine.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime, timezone
from math import isfinite
from statistics import mean
from typing import Any

from empire_os.lead_shadow_calibration_benchmark import evaluate_shadow_calibration
from empire_os.predictive_calibration import (
    ForecastActualEvidence, review_forecast_calibration,
)
from empire_os.predictive_calibration_board import build_predictive_calibration_board
from empire_os.predictive_materializer import ForecastMaterialization
from empire_os.predictive_revenue_scientific_readiness import (
    review_predictive_revenue_scientific_readiness,
)

METRIC = "recognized_revenue_cents"


def _time(value: str | datetime) -> datetime:
    try:
        result=(value if isinstance(value,datetime) else
                datetime.fromisoformat(str(value).replace("Z","+00:00")))
    except (ValueError, TypeError) as exc:
        raise ValueError("explicit valid diagnostic as_of required") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("timezone-aware diagnostic as_of required")
    return result.astimezone(timezone.utc)


def _forecast_reviews(
    pairs: Sequence[tuple[ForecastMaterialization,ForecastActualEvidence]],
    *, as_of:datetime,
) -> list:
    if type(pairs) not in (tuple,list) or len(pairs)>120:
        raise ValueError("bounded explicit forecast/actual pairs required")
    reviews=[]
    targets=set()
    for pair in pairs:
        if type(pair) is not tuple or len(pair)!=2:
            raise ValueError("forecast and actual evidence pair required")
        materialization,actual=pair
        if (not isinstance(materialization,ForecastMaterialization)
            or not isinstance(actual,ForecastActualEvidence)
            or materialization.write_authority!="none"):
            raise ValueError("original read-only forecast evidence required")
        if (materialization.metric!=METRIC or actual.metric!=METRIC
            or materialization.forecast.metric!=METRIC):
            raise ValueError("cannot mix forecast metrics with recognized revenue")
        if (actual.observed_date>as_of.date() or
            any(point.observed_date>as_of.date()
                for point in materialization.observations)):
            raise ValueError("future dated forecast actual evidence")
        if (not isinstance(actual.source,str) or
            not actual.source.startswith("canonical:commercial_events:") or
            not actual.source.removeprefix("canonical:commercial_events:").strip()):
            raise ValueError("canonical commercial event reference required")
        if (type(actual.actual_value) not in (float,int)
            or not isfinite(actual.actual_value) or actual.actual_value<0):
            raise ValueError("finite nonnegative actual required")
        forecast=materialization.forecast
        if forecast.predicted_value is not None and (
            type(forecast.predicted_value) not in (int,float) or
            not isfinite(forecast.predicted_value) or
            forecast.predicted_value<0
        ):
            raise ValueError("finite forecast required")
        review=review_forecast_calibration(
            materialization=materialization,actual=actual)
        target=(review.metric,review.actual_date)
        if target in targets:
            raise ValueError("duplicate forecast target would bias diagnostics")
        targets.add(target)
        reviews.append(review)
    return sorted(reviews,key=lambda row:row.actual_date)


def review_predictive_revenue_diagnostics(
    *, product_code:str, predictive_snapshot:Mapping[str,Any],
    economic_memory:Mapping[str,Any], tenant_id:str|None,
    as_of:str|datetime,
    forecast_actual_pairs:Sequence[
        tuple[ForecastMaterialization,ForecastActualEvidence]
    ]=(),
    min_prior_outcomes:int=20, min_evaluations:int=20,
    min_forecast_pairs:int=8, stale_after_days:int=30,
    source_provenance_gate:Mapping[str,Any]|None=None,
) -> dict[str,Any]:
    """Compile a review packet without promoting a predictor or writing data.

    The existing shadow evaluator independently replays canonical outcome
    lineage. Forecast-event identifiers are caller-provided and NOT validated
    against the commercial event store here: forecast deterioration is a
    descriptive review lead, not a verified revenue truth assertion.
    """
    now=_time(as_of)
    if (type(min_forecast_pairs) is not int or min_forecast_pairs<4
        or min_forecast_pairs>120 or min_forecast_pairs%2
        or type(stale_after_days) is not int or not 1<=stale_after_days<=365):
        raise ValueError("invalid predeclared diagnostic thresholds")
    if not isinstance(economic_memory,Mapping):
        raise ValueError("existing Economic Memory snapshot required")
    if not isinstance(predictive_snapshot,Mapping):
        raise ValueError("existing Predictive Intelligence snapshot required")
    if (economic_memory.get("tenant_id")!=tenant_id or
        predictive_snapshot.get("tenant_id")!=tenant_id):
        raise ValueError("tenant boundary mismatch")
    # Reuse the established product and verified-outcome cohort reader.
    readiness=review_predictive_revenue_scientific_readiness(
        product_code,predictive_snapshot)
    # Reuse original commercial prediction/outcome lineage verifier; never
    # substitute modeled chance scores or synthetic research outcomes.
    shadow=evaluate_shadow_calibration(
        economic_memory,tenant_id=tenant_id,as_of=now,
        min_history=min_prior_outcomes,min_evaluations=min_evaluations)
    reviews=_forecast_reviews(forecast_actual_pairs,as_of=now)
    board=build_predictive_calibration_board(reviews)
    ready=[row for row in reviews if row.calibration_ready]
    trend_status="NOT_ENOUGH_COMPARABLE_FORECAST_ACTUALS"
    first_error=last_error=delta=None
    if (len(ready)>=min_forecast_pairs and
        all(row.relative_error is not None and
            isfinite(row.relative_error) for row in ready)):
        first=ready[:len(ready)//2]
        last=ready[len(ready)//2:]
        first_error=round(mean(abs(row.relative_error) for row in first),6)
        last_error=round(mean(abs(row.relative_error) for row in last),6)
        delta=round(last_error-first_error,6)
        # Explicit review heuristics: not a validated statistical change
        # point, causal shift or proof of future forecast performance.
        trend_status=("DESCRIPTIVE_ERROR_DETERIORATION_REVIEW"
                      if delta>=0.10 and
                      last_error>=1.5*max(first_error,1e-9)
                      else "NO_LARGE_DESCRIPTIVE_ERROR_INCREASE")

    sources=[row.actual_date for row in ready]
    last_forecast=date.fromisoformat(max(sources)) if sources else None
    forecast_age=(now.date()-last_forecast).days if last_forecast else None
    shadow_reviews=economic_memory.get("calibration_evidence") or []
    # Timestamp safety of original reviews has already been rechecked inside
    # evaluate_shadow_calibration; no fresh labels can be invented here.
    last_commercial=None
    for row in shadow_reviews:
        t=_time(row["actual_at"])
        if last_commercial is None or t>last_commercial:
            last_commercial=t
    commercial_age=((now-last_commercial).days if last_commercial else None)
    blockers=list(shadow["blockers"])
    source_gate_status="NOT_REQUESTED"
    if source_provenance_gate is not None:
        if (not isinstance(source_provenance_gate,Mapping)
            or source_provenance_gate.get("schema_version")!=
                "empire.predictive_revenue.census_forecast_gate.v1"
            or source_provenance_gate.get("status")!=
                "READ_ONLY_SOURCE_EVIDENCE_HOLD"
            or source_provenance_gate.get("same_target_date") is not True
            or source_provenance_gate.get("eligible_for_revenue_forecast_calibration")
                is not False
            or source_provenance_gate.get("independent_database_forecast_proof")
                is not False
            or source_provenance_gate.get("immutable_daily_revenue_finality_proof")
                is not False
            or source_provenance_gate.get("tenant_access_authorized") is not False
            or source_provenance_gate.get("mode")!="OBSERVE"
            or source_provenance_gate.get("execution_authority")!="none"):
            raise ValueError("untrusted canonical source provenance gate")
        source_gate_status="SOURCE_CENSUS_AND_FORECAST_ORIGIN_NOT_FINAL"
        blockers.append("canonical_source_and_daily_revenue_finality_unverified")
    if readiness["product_cohorts_evidence_ready"]==0:
        blockers.append("no_product_cohort_with_verified_probability_and_timing")
    if forecast_age is None:
        blockers.append("no_comparable_recognized_revenue_forecast_actuals")
    elif forecast_age>stale_after_days:
        blockers.append("recognized_revenue_forecast_evidence_stale")
    if commercial_age is None:
        blockers.append("no_recent_verified_prediction_outcome")
    elif commercial_age>stale_after_days:
        blockers.append("verified_prediction_outcomes_stale")
    if trend_status=="NOT_ENOUGH_COMPARABLE_FORECAST_ACTUALS":
        blockers.append("insufficient_forecast_actual_trend_evidence")
    alerts=[]
    if trend_status=="DESCRIPTIVE_ERROR_DETERIORATION_REVIEW":
        alerts.append("recognized_revenue_forecast_error_deteriorated")
    if shadow["evaluation_ready"] is True and (
        shadow["candidate_beats_baseline"] is False):
        alerts.append("conversion_predictions_fail_historical_baseline")
    if any("stale" in item for item in blockers):
        alerts.append("commercial_evidence_freshness_review")
    # Missing evidence is a HOLD, never a zero-valued "healthy" outcome.
    status=("INSUFFICIENT_EVIDENCE_HOLD" if blockers else
            "HUMAN_REVIEW_RECOMMENDED" if alerts else
            "EVIDENCE_REVIEW_READY_NO_MAJOR_SIGNAL")
    recommended=[]
    if "recognized_revenue_forecast_error_deteriorated" in alerts:
        recommended.append("REVIEW_FORECAST_ERROR_EVIDENCE")
    if "conversion_predictions_fail_historical_baseline" in alerts:
        recommended.append("REVIEW_PREDICTION_CALIBRATION")
    if "commercial_evidence_freshness_review" in alerts:
        recommended.append("RECHECK_CANONICAL_EVIDENCE_FRESHNESS")
    if blockers:
        recommended.append("RESOLVE_VERIFIED_EVIDENCE_GAPS")
    return {
        "schema_version":"empire.predictive_revenue.diagnostic_intelligence.v1",
        "status":status,"mode":"OBSERVE",
        "product_code":readiness["product_code"],
        "tenant_bound":tenant_id is not None,
        "existing_product_readiness":readiness,
        "commercial_prediction_calibration":{
            "evaluation_ready":shadow["evaluation_ready"],
            "verified_review_count":shadow["verified_review_count"],
            "temporal_holdout_count":shadow["temporal_holdout_count"],
            "candidate_brier":shadow["candidate_brier"],
            "historical_baseline_brier":shadow["historical_baseline_brier"],
            "candidate_beats_baseline":shadow["candidate_beats_baseline"],
            "latest_evidence_age_days":commercial_age,
            "source":"validated_existing_economic_memory_shadow_review",
        },
        "recognized_revenue_forecast_review":{
            "review_count":board.review_count,
            "ready_review_count":board.ready_review_count,
            "mean_absolute_error_cents":board.mean_absolute_error,
            "mean_signed_relative_error":board.mean_relative_error,
            "trend_status":trend_status,
            "first_half_mean_absolute_relative_error":first_error,
            "last_half_mean_absolute_relative_error":last_error,
            "absolute_relative_error_increase":delta,
            "latest_actual_age_days":forecast_age,
            "source":"caller_attested_commercial_event_refs_not_db_reverified",
        },
        "review_alerts":sorted(set(alerts)),
        "recommended_review_steps":recommended,
        "human_review_required":bool(alerts or blockers),
        "blockers":sorted(set(blockers)),
        "canonical_source_evidence_review_status":source_gate_status,
        "source_provenance_can_promote_calibration":False,
        "synthetic_causal_model_used_for_revenue_probability":False,
        "drift_causality_claimed":False,
        "automatic_learning_promotion":False,
        "economic_memory_mutation":False,
        "forecast_mutation":False,
        "recognized_revenue_mutation":False,
        "buyer_or_tenant_data_written":False,
        "outbound_authorized":False,
        "payment_action":False,
        "execution_authority":"none",
    }
