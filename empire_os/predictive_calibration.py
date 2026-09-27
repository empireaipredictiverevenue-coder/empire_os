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
