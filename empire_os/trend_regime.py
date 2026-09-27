"""Deterministic trend/regime classification over canonical observed metrics."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import mean, pstdev
from typing import Any, Iterable

from empire_os.predictive_cloud_v3 import (
    DirectionalForecast,
    ObservedMetricPoint,
    forecast_observed_metric,
)


@dataclass(frozen=True)
class TrendRegime:
    available: bool
    metric: str
    trend: str
    regime: str
    sample_count: int
    volatility_ratio: float | None
    forecast: DirectionalForecast
    reason: str | None
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["forecast"] = self.forecast.as_dict()
        return data


def classify_trend_regime(
    *,
    metric: str,
    points: Iterable[ObservedMetricPoint],
    horizon_days: int = 7,
    volatile_threshold: float = 0.25,
) -> TrendRegime:
    rows = sorted(points, key=lambda point: point.observed_date)
    forecast = forecast_observed_metric(
        metric=metric,
        points=rows,
        horizon_days=horizon_days,
    )
    if not forecast.available:
        return TrendRegime(
            available=False,
            metric=metric,
            trend="insufficient_history",
            regime="insufficient_history",
            sample_count=len(rows),
            volatility_ratio=None,
            forecast=forecast,
            reason=forecast.reason,
        )

    values = [point.value for point in rows]
    avg = mean(values)
    volatility_ratio = 0.0 if avg == 0 else pstdev(values) / avg
    volatility_ratio = round(volatility_ratio, 4)

    if volatility_ratio >= volatile_threshold:
        regime = "volatile"
    elif forecast.direction == "up":
        regime = "expansion"
    elif forecast.direction == "down":
        regime = "contraction"
    else:
        regime = "stable"

    return TrendRegime(
        available=True,
        metric=metric,
        trend=forecast.direction,
        regime=regime,
        sample_count=len(rows),
        volatility_ratio=volatility_ratio,
        forecast=forecast,
        reason=None,
    )
