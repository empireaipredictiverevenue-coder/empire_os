"""Evidence-first Trend and Future-Trend Intelligence for Predictive Cloud.

This algorithm describes observed direction, velocity, acceleration and
persistence, then optionally estimates a future-opportunity alignment factor
when market saturation, competitive intensity and leading-indicator evidence
are present.

It does not turn search counts or model prose into market truth. Missing
structural inputs remain UNKNOWN and all forecasts remain non-actual.
"""
from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean
from typing import Any, Mapping, Sequence


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


def _time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _clean_observations(
    observations: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in observations:
        if not isinstance(raw, Mapping):
            continue
        observed_at = _time(raw.get("observed_at"))
        if observed_at is None or raw.get("value") is None:
            continue
        value = _number(raw["value"], "observation.value")
        source = str(raw.get("source") or "").strip()
        evidence_ref = str(raw.get("evidence_ref") or "").strip()
        if not source or not evidence_ref:
            continue
        rows.append({
            "observed_at": observed_at,
            "value": value,
            "source": source,
            "evidence_ref": evidence_ref,
        })
    rows.sort(key=lambda row: row["observed_at"])
    return rows


def _direction(value: float, epsilon: float = 1e-12) -> str:
    if value > epsilon:
        return "up"
    if value < -epsilon:
        return "down"
    return "flat"


def analyze_future_trend(
    observations: Sequence[Mapping[str, Any]],
    *,
    leading_indicator_strength: Any = None,
    market_saturation: Any = None,
    competitive_intensity: Any = None,
    now: datetime | None = None,
    freshness_window_days: float = 30.0,
) -> dict[str, Any]:
    """Build one deterministic Trend/Future-Trend packet."""
    rows = _clean_observations(observations)
    if len(rows) < 3:
        return {
            "schema_version": "empire.future_trend.v1",
            "status": "UNAVAILABLE",
            "reason": "insufficient_observed_time_series",
            "minimum_observations": 3,
            "observation_count": len(rows),
            "prediction_only": True,
            "actual_revenue": False,
            "execution_authority": "none",
        }

    first = rows[0]
    last = rows[-1]
    elapsed_days = (
        last["observed_at"] - first["observed_at"]
    ).total_seconds() / 86400.0
    if elapsed_days <= 0:
        return {
            "schema_version": "empire.future_trend.v1",
            "status": "UNAVAILABLE",
            "reason": "non_positive_observation_horizon",
            "observation_count": len(rows),
            "prediction_only": True,
            "actual_revenue": False,
            "execution_authority": "none",
        }

    deltas = [
        rows[index]["value"] - rows[index - 1]["value"]
        for index in range(1, len(rows))
    ]
    intervals = [
        max(
            (
                rows[index]["observed_at"]
                - rows[index - 1]["observed_at"]
            ).total_seconds() / 86400.0,
            1e-9,
        )
        for index in range(1, len(rows))
    ]
    velocities = [
        delta / days
        for delta, days in zip(deltas, intervals)
    ]
    velocity = mean(velocities)
    direction = _direction(velocity)

    midpoint = max(1, len(velocities) // 2)
    early_velocity = mean(velocities[:midpoint])
    late_velocity = mean(velocities[midpoint:]) if velocities[midpoint:] else velocity
    acceleration = late_velocity - early_velocity

    directional = [
        _direction(delta)
        for delta in deltas
        if _direction(delta) != "flat"
    ]
    persistence = (
        sum(item == direction for item in directional) / len(directional)
        if directional and direction != "flat"
        else 1.0 if not directional else 0.0
    )

    source_count = len({row["source"] for row in rows})
    source_diversity = min(1.0, source_count / 3.0)
    sample_strength = min(1.0, len(rows) / 12.0)

    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age_days = max(
        0.0,
        (current - last["observed_at"]).total_seconds() / 86400.0,
    )
    window = _number(freshness_window_days, "freshness_window_days")
    if window <= 0:
        raise ValueError("freshness_window_days must be positive")
    freshness = max(0.0, 1.0 - (age_days / window))

    confidence = (
        persistence
        * source_diversity
        * sample_strength
        * freshness
    ) ** 0.25

    base = {
        "schema_version": "empire.future_trend.v1",
        "status": "AVAILABLE",
        "observation_count": len(rows),
        "source_count": source_count,
        "horizon_days": round(elapsed_days, 6),
        "direction": direction,
        "velocity_per_day": round(velocity, 8),
        "acceleration_per_day": round(acceleration, 8),
        "persistence": round(persistence, 6),
        "source_diversity": round(source_diversity, 6),
        "sample_strength": round(sample_strength, 6),
        "freshness": round(freshness, 6),
        "trend_confidence": round(confidence, 6),
        "latest_value": last["value"],
        "evidence_refs": list(
            dict.fromkeys(row["evidence_ref"] for row in rows)
        ),
        "prediction_only": True,
        "causal_claim": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }

    structural = {
        "leading_indicator_strength": leading_indicator_strength,
        "market_saturation": market_saturation,
        "competitive_intensity": competitive_intensity,
    }
    missing = [
        name for name, value in structural.items()
        if value is None
    ]
    if missing:
        return {
            **base,
            "future_opportunity_status": "UNAVAILABLE",
            "future_opportunity_missing_fields": missing,
            "trend_opportunity_alignment": None,
            "unknown_is_zero": False,
        }

    leading = _probability(
        leading_indicator_strength,
        "leading_indicator_strength",
    )
    saturation = _probability(
        market_saturation,
        "market_saturation",
    )
    competition = _probability(
        competitive_intensity,
        "competitive_intensity",
    )

    direction_factor = (
        1.0 if direction == "up"
        else 0.5 if direction == "flat"
        else 0.0
    )
    acceleration_factor = (
        1.0 if acceleration > 0
        else 0.5 if abs(acceleration) <= 1e-12
        else 0.0
    )
    headroom = 1.0 - saturation
    competitive_headroom = 1.0 - competition

    alignment = (
        direction_factor
        * (0.5 + 0.5 * acceleration_factor)
        * leading
        * headroom
        * competitive_headroom
        * confidence
    )

    return {
        **base,
        "future_opportunity_status": "AVAILABLE",
        "leading_indicator_strength": leading,
        "market_saturation": saturation,
        "competitive_intensity": competition,
        "market_headroom": round(headroom, 6),
        "competitive_headroom": round(competitive_headroom, 6),
        "trend_opportunity_alignment": round(alignment, 6),
        "unknown_is_zero": False,
    }
