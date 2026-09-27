"""Search traffic forecast bundle: impressions, clicks and CTR.

Observed Search Console metrics remain truth. Baseline and TimesFM outputs are
modeled forecasts only and cannot create revenue or trigger external actions.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Iterable, Mapping

from empire_os.predictive_cloud_v3 import (
    ObservedMetricPoint,
    forecast_observed_metric,
)
from empire_os.timesfm_shadow import (
    DisabledTimesFmProvider,
    TimesFmProvider,
)


@dataclass(frozen=True)
class DailySearchObservation:
    observed_date: date
    impressions: float
    clicks: float
    source: str = "google_search_console"

    def validate(self) -> None:
        if self.impressions < 0 or self.clicks < 0:
            raise ValueError("search observations must be nonnegative")
        if self.clicks > self.impressions and self.impressions >= 0:
            raise ValueError("clicks cannot exceed impressions")
        if not self.source.strip():
            raise ValueError("source provenance required")

    @property
    def ctr(self) -> float | None:
        if self.impressions <= 0:
            return None
        return self.clicks / self.impressions


@dataclass(frozen=True)
class SearchTrafficForecastBundle:
    available: bool
    horizon_days: int
    context_days: int
    latest_impressions: float | None
    latest_clicks: float | None
    latest_ctr: float | None
    baseline_impressions: dict[str, Any]
    baseline_clicks: dict[str, Any]
    timesfm_impressions: dict[str, Any]
    timesfm_clicks: dict[str, Any]
    timesfm_horizon_impressions: float | None
    timesfm_horizon_clicks: float | None
    timesfm_horizon_ctr: float | None
    reason: str | None
    mode: str = "SHADOW_COMPARE"
    execution_authority: str = "none"
    creates_actuals: bool = False
    creates_revenue: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def aggregate_search_console_daily(
    rows: Iterable[Mapping[str, Any]],
) -> list[DailySearchObservation]:
    totals: dict[date, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for row in rows:
        keys = row.get("keys")
        if not isinstance(keys, (list, tuple)) or not keys:
            continue
        try:
            observed = date.fromisoformat(str(keys[0]))
            impressions = float(row.get("impressions") or 0)
            clicks = float(row.get("clicks") or 0)
        except (TypeError, ValueError):
            continue
        if impressions < 0 or clicks < 0:
            raise ValueError("search observations must be nonnegative")
        totals[observed][0] += impressions
        totals[observed][1] += clicks

    output = [
        DailySearchObservation(
            observed_date=day,
            impressions=values[0],
            clicks=values[1],
        )
        for day, values in sorted(totals.items())
    ]
    for item in output:
        item.validate()
    return output


def forecast_search_traffic(
    observations: Iterable[DailySearchObservation],
    *,
    horizon_days: int,
    timesfm_provider: TimesFmProvider | None = None,
) -> SearchTrafficForecastBundle:
    rows = sorted(observations, key=lambda item: item.observed_date)
    for row in rows:
        row.validate()

    horizon = int(horizon_days)
    if horizon < 1 or horizon > 365:
        raise ValueError("horizon_days out of bounds")

    impression_points = [
        ObservedMetricPoint(
            observed_date=row.observed_date,
            value=row.impressions,
            source=row.source,
        )
        for row in rows
    ]
    click_points = [
        ObservedMetricPoint(
            observed_date=row.observed_date,
            value=row.clicks,
            source=row.source,
        )
        for row in rows
    ]
    baseline_impressions = forecast_observed_metric(
        metric="search_impressions",
        points=impression_points,
        horizon_days=horizon,
    )
    baseline_clicks = forecast_observed_metric(
        metric="search_clicks",
        points=click_points,
        horizon_days=horizon,
    )

    provider = timesfm_provider or DisabledTimesFmProvider()
    timesfm_impressions = provider.forecast(
        metric="search_impressions",
        values=[row.impressions for row in rows],
        horizon_steps=horizon,
    )
    timesfm_clicks = provider.forecast(
        metric="search_clicks",
        values=[row.clicks for row in rows],
        horizon_steps=horizon,
    )

    horizon_impressions = (
        round(sum(timesfm_impressions.point_forecast), 2)
        if timesfm_impressions.available
        else None
    )
    horizon_clicks = (
        round(sum(timesfm_clicks.point_forecast), 2)
        if timesfm_clicks.available
        else None
    )
    horizon_ctr = (
        round(horizon_clicks / horizon_impressions, 6)
        if horizon_clicks is not None
        and horizon_impressions is not None
        and horizon_impressions > 0
        else None
    )
    latest = rows[-1] if rows else None
    available = bool(
        baseline_impressions.available
        or baseline_clicks.available
        or timesfm_impressions.available
        or timesfm_clicks.available
    )
    reason = (
        None if available
        else baseline_impressions.reason
        or baseline_clicks.reason
        or timesfm_impressions.reason
        or timesfm_clicks.reason
    )

    return SearchTrafficForecastBundle(
        available=available,
        horizon_days=horizon,
        context_days=len(rows),
        latest_impressions=latest.impressions if latest else None,
        latest_clicks=latest.clicks if latest else None,
        latest_ctr=(
            round(latest.ctr, 6)
            if latest and latest.ctr is not None
            else None
        ),
        baseline_impressions=baseline_impressions.as_dict(),
        baseline_clicks=baseline_clicks.as_dict(),
        timesfm_impressions=timesfm_impressions.as_dict(),
        timesfm_clicks=timesfm_clicks.as_dict(),
        timesfm_horizon_impressions=horizon_impressions,
        timesfm_horizon_clicks=horizon_clicks,
        timesfm_horizon_ctr=horizon_ctr,
        reason=reason,
    )
