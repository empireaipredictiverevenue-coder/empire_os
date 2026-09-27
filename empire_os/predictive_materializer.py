"""Canonical daily-actual materializer for Predictive Cloud V3."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Mapping, Sequence

from empire_os.predictive_cloud_v3 import (
    DirectionalForecast,
    ObservedMetricPoint,
    forecast_observed_metric,
)


@dataclass(frozen=True)
class ForecastMaterialization:
    metric: str
    observations: tuple[ObservedMetricPoint, ...]
    forecast: DirectionalForecast
    write_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "observations": [
                {
                    "observed_date": point.observed_date.isoformat(),
                    "value": point.value,
                    "source": point.source,
                }
                for point in self.observations
            ],
            "forecast": self.forecast.as_dict(),
            "write_authority": self.write_authority,
        }


def materialize_daily_actuals(
    *,
    metric: str,
    rows: Sequence[Mapping[str, Any]],
    value_field: str,
    date_field: str,
    horizon_days: int,
) -> ForecastMaterialization:
    name = str(metric or "").strip()
    if not name:
        raise ValueError("metric required")
    if not value_field or not date_field:
        raise ValueError("value_field and date_field required")

    by_date: dict[date, ObservedMetricPoint] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("canonical actual row must be a mapping")
        if row.get(value_field) is None or row.get(date_field) is None:
            raise ValueError("canonical actual row missing required fields")
        source = str(row.get("source") or "").strip()
        if not source:
            raise ValueError("canonical actual row requires source provenance")

        observed_date = date.fromisoformat(str(row[date_field]))
        value = float(row[value_field])
        if value < 0:
            raise ValueError("canonical actual values must be nonnegative")

        point = ObservedMetricPoint(
            observed_date=observed_date,
            value=value,
            source=source,
        )
        existing = by_date.get(observed_date)
        if existing and existing.value != point.value:
            raise ValueError("conflicting canonical actuals for observed date")
        by_date[observed_date] = point

    observations = tuple(by_date[key] for key in sorted(by_date))
    forecast = forecast_observed_metric(
        metric=name,
        points=observations,
        horizon_days=horizon_days,
    )
    return ForecastMaterialization(
        metric=name,
        observations=observations,
        forecast=forecast,
    )
