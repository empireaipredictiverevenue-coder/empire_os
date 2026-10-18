"""Phase 10 evidence-only forecast realization calibration."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any

from empire_os.predictive_materializer import ForecastMaterialization


@dataclass(frozen=True)
class ForecastActualEvidence:
    metric: str
    observed_date: date
    actual_value: float
    source: str

    def validate(self) -> None:
        if not self.metric.strip():
            raise ValueError("metric required")
        if self.actual_value < 0:
            raise ValueError("actual_value must be nonnegative")
        if not self.source.strip():
            raise ValueError("actual outcome requires source provenance")


@dataclass(frozen=True)
class ForecastCalibrationReview:
    metric: str
    target_date: str | None
    actual_date: str
    predicted_value: float | None
    actual_value: float
    signed_error: float | None
    absolute_error: float | None
    relative_error: float | None
    bias: str
    calibration_ready: bool
    blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    mode: str = "OBSERVE"
    execution_authority: str = "none"
    forecast_mutation: bool = False
    model_weight_mutation: bool = False
    commercial_execution: bool = False
    accounting_mutation: bool = False
    creates_actual_revenue: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _bias(error: float | None) -> str:
    if error is None:
        return "unknown"
    if abs(error) <= 1e-9:
        return "on_target"
    if error > 0:
        return "under_predicted"
    return "over_predicted"


def review_forecast_calibration(
    *,
    materialization: ForecastMaterialization,
    actual: ForecastActualEvidence,
) -> ForecastCalibrationReview:
    actual.validate()
    forecast = materialization.forecast
    blockers: list[str] = []
    refs = [actual.source]
    target_date: date | None = None

    if materialization.metric != actual.metric or forecast.metric != actual.metric:
        raise ValueError("forecast/actual metric mismatch")

    if not materialization.observations:
        blockers.append("forecast_observation_history_missing")
    else:
        target_date = (
            materialization.observations[-1].observed_date
            + timedelta(days=forecast.horizon_days)
        )
        if actual.observed_date != target_date:
            blockers.append("actual_date_does_not_match_forecast_target")

    if not forecast.available or forecast.predicted_value is None:
        blockers.append("forecast_not_available_for_calibration")

    signed = absolute = relative = None
    if not blockers and forecast.predicted_value is not None:
        signed = round(actual.actual_value - forecast.predicted_value, 4)
        absolute = round(abs(signed), 4)
        if forecast.predicted_value > 0:
            relative = round(signed / forecast.predicted_value, 4)

    ordered = tuple(sorted(set(blockers)))
    return ForecastCalibrationReview(
        metric=actual.metric,
        target_date=(target_date.isoformat() if target_date else None),
        actual_date=actual.observed_date.isoformat(),
        predicted_value=forecast.predicted_value,
        actual_value=actual.actual_value,
        signed_error=signed,
        absolute_error=absolute,
        relative_error=relative,
        bias=_bias(signed),
        calibration_ready=not ordered,
        blockers=ordered,
        evidence_refs=tuple(dict.fromkeys(refs)),
    )


def review_commercial_prediction(*, prediction, feedback, tenant_id, as_of):
    """Resolve an explicit probability prediction using existing Quant Brier scoring."""
    from copy import deepcopy
    from datetime import datetime
    from empire_os.outcome_feedback import validate_verified_feedback
    from empire_os.quant_brain import brier_score

    def timestamp(value):
        time = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if time.tzinfo is None:
            raise ValueError('timezone-aware prediction evidence required')
        return time

    validate_verified_feedback(feedback, tenant_id=tenant_id, as_of=as_of)
    if prediction.get('tenant_id') != tenant_id:
        raise ValueError('prediction tenant mismatch')
    for key in ('opportunity_key', 'prediction_ref'):
        if not isinstance(prediction.get(key), str) or not prediction[key] or prediction[key] != feedback.get(key):
            raise ValueError('prediction/outcome lineage mismatch or missing')
    if prediction.get('prediction_type') != 'conversion_probability':
        raise ValueError('unsupported commercial prediction type')
    if not prediction.get('evidence_refs'):
        raise ValueError('original prediction evidence required')
    predicted_at = timestamp(prediction.get('predicted_at'))
    actual_at = timestamp(feedback['available_at'])
    horizon = timestamp(prediction.get('horizon_until'))
    if not predicted_at < timestamp(feedback['outcome_recorded_at']) <= actual_at <= horizon:
        raise ValueError('outcome outside original prediction window')
    probability = prediction.get('predicted_probability')
    if isinstance(probability, bool):
        raise ValueError('invalid probability')
    metric = brier_score([probability], [feedback['verified_label']])
    residual = round(feedback['verified_label'] - probability, 6)
    return dict(schema_version='empire.commercial_prediction_calibration.v1',
        tenant_id=tenant_id, opportunity_key=prediction['opportunity_key'],
        prediction_ref=prediction['prediction_ref'], decision_ref=feedback.get('decision_ref'),
        execution_ref=feedback.get('execution_ref'), outcome_ref=feedback['outcome_ref'],
        prediction_type='conversion_probability', predicted_value=probability,
        predicted_at=predicted_at.isoformat(), horizon_until=horizon.isoformat(),
        actual_value=feedback['verified_label'], actual_at=actual_at.isoformat(),
        signed_error=residual, brier_score=metric['brier_score'],
        evidence_refs=list(dict.fromkeys([*prediction['evidence_refs'], *feedback['evidence_refs']])),
        prediction=deepcopy(prediction), feedback=deepcopy(feedback),
        calibration_ready=True, learning_stage='SHADOW_LEARNING', shadow_only=True,
        model_weight_mutation=False, promoted_learning=False, execution_authority='none')


def prepare_prospective_conversion_prediction(
    *,
    tenant_id: str,
    opportunity_key: str,
    predicted_probability: float,
    predicted_at: str,
    horizon_until: str,
    evidence_refs: list[str] | tuple[str, ...],
    model_name: str,
    model_version: str,
    assessed_at: datetime,
) -> dict[str, Any]:
    """Prepare an original forecast *candidate* before future commercial results.

    This is a deterministic input contract, NOT an immutable registry receipt.
    Its creation does not prove what was known historically; canonical recording
    and a separate trusted pre-outcome readback remain required. It deliberately
    never sets original_prediction_registered=True or activates learning.
    """
    from datetime import datetime
    from hashlib import sha256
    from math import isfinite
    import json

    def required(value, name):
        if (not isinstance(value, str) or not value.strip()
                or value != value.strip() or len(value) > 128):
            raise ValueError(f"{name} required and bounded")
        return value

    def timestamp(value, name):
        if not isinstance(value, str) or len(value) > 60:
            raise ValueError(f"{name} timestamp required")
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{name} timestamp invalid") from exc
        if result.utcoffset() is None:
            raise ValueError(f"{name} timezone required")
        return result

    tenant = required(tenant_id, "tenant_id")
    opportunity = required(opportunity_key, "opportunity_key")
    model = required(model_name, "model_name")
    version = required(model_version, "model_version")
    if (type(predicted_probability) not in (int, float)
            or not isfinite(predicted_probability)
            or not 0 <= predicted_probability <= 1):
        raise ValueError("finite predicted_probability between 0 and 1 required")
    if not isinstance(assessed_at, datetime) or assessed_at.utcoffset() is None:
        raise ValueError("assessed_at timezone required")
    predicted = timestamp(predicted_at, "predicted_at")
    horizon = timestamp(horizon_until, "horizon_until")
    if not (predicted <= assessed_at < horizon):
        raise ValueError("prospective forecast timestamps required")
    if not isinstance(evidence_refs, (list, tuple)) or not 1 <= len(evidence_refs) <= 20:
        raise ValueError("bounded original evidence refs required")
    if (any(not isinstance(ref, str) or not ref.strip()
            or ref != ref.strip() or len(ref) > 240 for ref in evidence_refs)
            or len(set(evidence_refs)) != len(evidence_refs)):
        raise ValueError("distinct original evidence refs required")
    # Do not infer a conversion likelihood from general opportunity scores.
    # A probability here is provided explicitly by the upstream model, and
    # must be durably registered before an eventual outcome can be evaluated.
    canonical = {
        "tenant_id": tenant,
        "opportunity_key": opportunity,
        "prediction_type": "conversion_probability",
        "predicted_probability": float(predicted_probability),
        "predicted_at": predicted.isoformat(),
        "horizon_until": horizon.isoformat(),
        "model_name": model,
        "model_version": version,
        "evidence_refs": sorted(evidence_refs),
    }
    material = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    ref = "conversion_prediction_candidate:" + sha256(material.encode()).hexdigest()[:32]
    return {
        "schema_version": "empire.original_conversion_prediction_preflight.v1",
        "status": "REGISTRY_PROOF_REQUIRED",
        "candidate_prediction_ref": ref,
        "proposed_prediction": dict(canonical, prediction_ref=ref),
        "original_prediction_registered": False,
        "canonical_registry_readback_verified": False,
        "pre_outcome_immutability_proven": False,
        "source_refs_independently_authenticated": False,
        "may_use_in_verified_calibration": False,
        "must_store_in_existing_canonical_prediction_registry": False,
        "requires_dedicated_original_conversion_registry": True,
        "destination_registry_kind": "original_conversion_predictions_STAGED_NOT_ACTIVATED",
        "no_prediction_accuracy_claim": True,
        "prediction_only": True,
        "actual_revenue": False,
        "execution_authority": "none",
        "database_writes": False,
        "outbound_sent": False,
        "payments_moved": False,
    }
