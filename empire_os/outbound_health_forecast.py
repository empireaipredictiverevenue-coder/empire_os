"""Bounded trend forecast for outbound reputation health.

Forecasts metric-threshold pressure from recent observations. This is an early-warning
heuristic, not a guarantee of future inbox placement or provider behavior.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping


def _slope(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    n = len(values)
    xs = list(range(n))
    x_mean = sum(xs) / n
    y_mean = sum(values) / n
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, values))
    denominator = sum((x - x_mean) ** 2 for x in xs)
    return numerator / denominator if denominator else 0.0


def _horizon(current: float, slope: float, threshold: float, worsening_up: bool) -> int | None:
    if worsening_up:
        if current >= threshold:
            return 0
        if slope <= 0:
            return None
        distance = threshold - current
    else:
        if current <= threshold:
            return 0
        if slope >= 0:
            return None
        distance = current - threshold
        slope = abs(slope)
    windows = int(distance / slope)
    return max(1, windows)


def forecast_reputation_health(
    observations: Iterable[Mapping[str, Any]],
    *,
    bounce_hold: float = 0.03,
    complaint_hold: float = 0.0008,
    placement_hold: float = 0.90,
    warning_horizon_windows: int = 3,
) -> dict[str, Any]:
    rows = [dict(row) for row in observations]
    if len(rows) < 2:
        return {
            "posture": "INSUFFICIENT_HISTORY",
            "forecasts": {},
            "claim": "bounded_trend_forecast_not_provider_prediction",
        }

    specs = {
        "bounce_rate": (bounce_hold, True),
        "complaint_rate": (complaint_hold, True),
        "inbox_placement_rate": (placement_hold, False),
    }
    forecasts: dict[str, Any] = {}
    imminent = []

    for metric, (threshold, worsening_up) in specs.items():
        values = []
        for row in rows:
            if row.get(metric) is None:
                continue
            values.append(float(row[metric]))
        if len(values) < 2:
            continue

        slope = _slope(values)
        current = values[-1]
        horizon = _horizon(current, slope, threshold, worsening_up)
        direction = (
            "WORSENING"
            if (worsening_up and slope > 0) or ((not worsening_up) and slope < 0)
            else "IMPROVING"
            if slope != 0
            else "STABLE"
        )
        forecasts[metric] = {
            "current": current,
            "slope_per_window": round(slope, 8),
            "threshold": threshold,
            "direction": direction,
            "estimated_windows_to_threshold": horizon,
        }
        if horizon is not None and horizon <= warning_horizon_windows:
            imminent.append(metric)

    posture = "PREEMPTIVE_THROTTLE" if imminent else "OBSERVE"
    return {
        "posture": posture,
        "imminent_thresholds": imminent,
        "forecasts": forecasts,
        "claim": "bounded_trend_forecast_not_provider_prediction",
    }
