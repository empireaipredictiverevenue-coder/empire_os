"""Phase 10 Predictive Cloud V3 evidence-backed forecast foundation."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Iterable, Sequence


MIN_FORECAST_SAMPLES = 7
MAX_FORECAST_HORIZON_DAYS = 365


@dataclass(frozen=True)
class ObservedMetricPoint:
    observed_date: date
    value: float
    source: str


@dataclass(frozen=True)
class DirectionalForecast:
    available: bool
    metric: str
    horizon_days: int
    sample_count: int
    latest_observed_value: float | None
    predicted_value: float | None
    daily_slope: float | None
    r_squared: float | None
    evidence_confidence: float | None
    direction: str
    reason: str | None
    source: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
def _sorted_points(points: Iterable[ObservedMetricPoint]) -> list[ObservedMetricPoint]:
    rows = sorted(points, key=lambda point: point.observed_date)
    if any(point.value < 0 for point in rows):
        raise ValueError("observed metric values must be nonnegative")
    if any(not point.source.strip() for point in rows):
        raise ValueError("every observed point requires provenance")
    return rows


def _linear_fit(values: Sequence[float]) -> tuple[float, float, float]:
    n = len(values)
    xs = list(range(n))
    x_mean = sum(xs) / n
    y_mean = sum(values) / n

    denom = sum((x - x_mean) ** 2 for x in xs)
    slope = (
        sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, values))
        / denom
        if denom
        else 0.0
    )
    intercept = y_mean - slope * x_mean

    fitted = [intercept + slope * x for x in xs]
    ss_res = sum((y - y_hat) ** 2 for y, y_hat in zip(values, fitted))
    ss_tot = sum((y - y_mean) ** 2 for y in values)
    r_squared = 1.0 if ss_tot == 0 else max(0.0, min(1.0, 1 - ss_res / ss_tot))
    return slope, intercept, r_squared


def forecast_observed_metric(
    *,
    metric: str,
    points: Iterable[ObservedMetricPoint],
    horizon_days: int,
) -> DirectionalForecast:
    metric_name = str(metric or "").strip()
    if not metric_name:
        raise ValueError("metric is required")
    horizon = int(horizon_days)
    if horizon < 1 or horizon > MAX_FORECAST_HORIZON_DAYS:
        raise ValueError("forecast horizon out of bounds")

    rows = _sorted_points(points)
    source = "canonical_observed_time_series"
    if len(rows) < MIN_FORECAST_SAMPLES:
        return DirectionalForecast(
            available=False,
            metric=metric_name,
            horizon_days=horizon,
            sample_count=len(rows),
            latest_observed_value=(rows[-1].value if rows else None),
            predicted_value=None,
            daily_slope=None,
            r_squared=None,
            evidence_confidence=None,
            direction="insufficient_history",
            reason=f"minimum_{MIN_FORECAST_SAMPLES}_observations_required",
            source=source,
        )

    values = [point.value for point in rows]
    slope, intercept, r_squared = _linear_fit(values)
    target_x = (len(values) - 1) + horizon
    predicted = max(0.0, intercept + slope * target_x)

    epsilon = 1e-9
    if slope > epsilon:
        direction = "up"
    elif slope < -epsilon:
        direction = "down"
    else:
        direction = "flat"

    sample_factor = min(1.0, len(rows) / 30.0)
    confidence = round(r_squared * sample_factor, 4)

    return DirectionalForecast(
        available=True,
        metric=metric_name,
        horizon_days=horizon,
        sample_count=len(rows),
        latest_observed_value=rows[-1].value,
        predicted_value=round(predicted, 2),
        daily_slope=round(slope, 4),
        r_squared=round(r_squared, 4),
        evidence_confidence=confidence,
        direction=direction,
        reason=None,
        source=source,
    )
