"""Point-in-time Trend & Future-Trend Intelligence; OBSERVE-only research.

Extends existing future_trend_intelligence rather than creating another agent.
One homogeneous market metric per series. Original source records are untrusted
until the owning source/tenant identity, acquisition rights and original
historical availability have been independently authenticated.

Directional drift is an illustrative scenario, never an empirical probability,
monetary forecast, statistically validated interval or customer activation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from math import isfinite
from statistics import mean
import json
from typing import Any

from empire_os.future_trend_intelligence import analyze_future_trend

SCHEMA = "empire.predictive_intelligence.future_trend_horizons.v1"
MAX_ROWS = 500
HORIZONS = (7, 30, 90)
KINDS = frozenset((
    "search_interest_index", "first_party_intent_count",
    "project_permit_count", "publisher_inventory_count",
    "official_leading_indicator_index",
))
UNITS = frozenset(("index_0_100", "count", "index_points"))


class TrendHorizonHold(ValueError):
    """Fail closed, avoiding original customer IDs and source values in errors."""


def _date(value: Any) -> datetime:
    if type(value) is not str or not 19 <= len(value) <= 48:
        raise TrendHorizonHold("timezone-aware timestamp required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("timezone absent")
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise TrendHorizonHold("invalid timestamp") from None


def _unit_value(value: Any, unit: str) -> float:
    if type(value) not in (int, float) or not isfinite(value) or value < 0:
        raise TrendHorizonHold("finite nonnegative source metric required")
    if unit == "count" and (type(value) is not int or value > 10**9):
        raise TrendHorizonHold("original count must be bounded integer")
    if unit == "index_0_100" and value > 100:
        raise TrendHorizonHold("normalised index must stay between 0 and 100")
    if unit == "index_points" and value > 10**9:
        raise TrendHorizonHold("source index exceeds bound")
    return float(value)


def _record(raw: Any, *, expected: dict[str, str], review: datetime) -> dict:
    exact = {
        "series_id", "source_kind", "unit", "geography", "vertical",
        "source_name", "observed_at", "first_available_at", "ingested_at",
        "value", "revision", "evidence_sha256",
    }
    if type(raw) is not dict or set(raw) != exact:
        raise TrendHorizonHold("invalid trend source envelope")
    for field, value in expected.items():
        if raw[field] != value:
            raise TrendHorizonHold("incomparable market series mixed")
    if (type(raw["revision"]) is not int or
            not 1 <= raw["revision"] <= 1_000_000 or
            type(raw["evidence_sha256"]) is not str or
            len(raw["evidence_sha256"]) != 64 or
            any(c not in "0123456789abcdef" for c in raw["evidence_sha256"])):
        raise TrendHorizonHold("source revision/digest invalid")
    observed = _date(raw["observed_at"])
    available = _date(raw["first_available_at"])
    ingested = _date(raw["ingested_at"])
    if not (observed <= available <= ingested <= review):
        raise TrendHorizonHold("source availability clock invalid")
    return {
        "observed": observed,
        "available": available,
        "ingested": ingested,
        "value": _unit_value(raw["value"], expected["unit"]),
        "revision": raw["revision"],
        "sha": raw["evidence_sha256"],
    }


def _mae_outcomes(rows: list[dict], all_asof_revisions: list[dict]) -> dict:
    # Rolling-origin one-step-ahead validation. A historic fold MUST be
    # reconstructed from revisions already available before the target event.
    # Latest revisions known today may never leak into earlier train windows.
    naive_errors, drift_errors = [], []
    for end in range(5, len(rows)):
        test = rows[end]
        cutoff = test["observed"]
        fold_versions: dict[datetime,dict] = {}
        for item in all_asof_revisions:
            if (item["observed"] >= cutoff or item["available"] >= cutoff
                    or item["ingested"] >= cutoff):
                continue
            earlier = fold_versions.get(item["observed"])
            if earlier is None or item["revision"] > earlier["revision"]:
                fold_versions[item["observed"]] = item
        train = [fold_versions[k] for k in sorted(fold_versions)]
        if len(train) < 5:
            continue
        dt = (test["observed"] - train[-1]["observed"]).total_seconds() / 86400
        span = (train[-1]["observed"] - train[0]["observed"]).total_seconds() / 86400
        if dt <= 0 or span <= 0:
            raise TrendHorizonHold("nonpositive historical interval")
        naive = train[-1]["value"]
        drift = max(0., naive + (naive - train[0]["value"]) / span * dt)
        naive_errors.append(abs(naive - test["value"]))
        drift_errors.append(abs(drift - test["value"]))
    if len(drift_errors) < 4:
        return {
            "method": "CHRONOLOGICAL_ONE_STEP_DRIFT_VS_NAIVE",
            "fold_count": len(drift_errors),
            "naive_mae": None,
            "drift_mae": None,
            "drift_beats_naive": None,
            "validation_status": "INSUFFICIENT_ROLLING_WINDOWS",
        }
    naive_mae = mean(naive_errors)
    drift_mae = mean(drift_errors)
    beats = drift_mae < naive_mae * 0.9 and naive_mae > 0
    return {
        "method": "CHRONOLOGICAL_ONE_STEP_DRIFT_VS_NAIVE",
        "fold_count": len(drift_errors),
        "naive_mae": round(naive_mae, 6),
        "drift_mae": round(drift_mae, 6),
        "drift_beats_naive": beats,
        "validation_status": (
            "DRIFT_BEATS_NAIVE_RESEARCH_BASELINE"
            if beats else "DRIFT_NOT_BETTER_THAN_NAIVE"
        ),
    }


def review_trend_horizons(
    observations: Any, *, as_of: str, review_at: str,
    series_id: str, source_kind: str, unit: str,
    geography: str, vertical: str, source_name: str,
) -> dict[str, Any]:
    """Produce reproducible trend signals without live execution authority."""
    cutoff, now = _date(as_of), _date(review_at)
    if cutoff > now or type(observations) not in (tuple, list) or len(observations) > MAX_ROWS:
        raise TrendHorizonHold("bounded as-of series required")
    expected = dict(
        series_id=series_id, source_kind=source_kind, unit=unit,
        geography=geography, vertical=vertical, source_name=source_name,
    )
    if (source_kind not in KINDS or unit not in UNITS
            or (source_kind == "search_interest_index" and unit != "index_0_100")
            or (source_kind.endswith("_count") and unit != "count")
            or any(type(v) is not str or not 1 <= len(v) <= 100
                   for v in expected.values())):
        raise TrendHorizonHold("inconsistent original source measurement contract")
    revisions: dict[datetime, dict] = {}
    seen: set[tuple[datetime,int]] = set()
    withheld = 0
    eligible_revisions: list[dict] = []
    for raw in observations:
        item = _record(raw, expected=expected, review=now)
        key = (item["observed"], item["revision"])
        if key in seen:
            raise TrendHorizonHold("duplicate source revision")
        seen.add(key)
        if (item["observed"] > cutoff or
                item["available"] > cutoff or item["ingested"] > cutoff):
            withheld += 1
            continue
        eligible_revisions.append(item)
        previous = revisions.get(item["observed"])
        if previous is None or item["revision"] > previous["revision"]:
            revisions[item["observed"]] = item
    ordered = [revisions[k] for k in sorted(revisions)]
    digest_rows = [
        [r["observed"].isoformat(), r["available"].isoformat(),
         r["ingested"].isoformat(), r["value"], r["revision"], r["sha"]]
        for r in ordered
    ]
    manifest = sha256(json.dumps(
        dict(series=expected, as_of=cutoff.isoformat(), observations=digest_rows),
        sort_keys=True, separators=(",",":"), allow_nan=False,
    ).encode()).hexdigest()
    base = {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "INSUFFICIENT_POINT_IN_TIME_HISTORY",
        "as_of": cutoff.isoformat(),
        "review_at": now.isoformat(),
        "source_kind": source_kind,
        "metric_unit": unit,
        "horizon_days": list(HORIZONS),
        "source_row_count": len(observations),
        "late_or_future_revisions_withheld": withheld,
        "distinct_as_of_observations": len(ordered),
        "source_manifest_sha256_change_detection_only": manifest,
        "source_owner_authenticated": False,
        "tenant_and_usage_rights_verified": False,
        "google_trends_index_is_not_absolute_search_volume": source_kind=="search_interest_index",
        "cross_source_numeric_fusion_used": False,
        "calibrated_prediction_intervals_available": False,
        "forecast_accuracy_verified_on_customer_outcomes": False,
        "original_conversion_registry_verified": False,
        "actual_revenue": False,
        "commercial_forecast_authorized": False,
        "outbound_or_payment_action": False,
        "database_writes": False,
        "execution_authority": "none",
    }
    if len(ordered) < 9:
        return {**base, "rolling_validation_status": "INSUFFICIENT_HISTORY",
                "future_scenarios": [], "future_opportunity_status": "UNAVAILABLE"}
    # Refuse backtests with irregular or huge temporal gaps: drift on an
    # inconsistent timeline is not an equivalent next-period baseline.
    intervals = [
        (ordered[i]["observed"] - ordered[i-1]["observed"]).total_seconds()/86400
        for i in range(1,len(ordered))
    ]
    if any(v <= 0 for v in intervals) or max(intervals) > 2 * min(intervals):
        return {**base, "status": "IRREGULAR_SAMPLING_REQUIRES_OWNER_REVIEW",
                "rolling_validation_status": "NOT_RUN",
                "future_scenarios": [], "future_opportunity_status": "UNAVAILABLE"}
    # The existing trend module computes direction, acceleration and
    # persistence; we do not give it a made-up saturation/competition score.
    trend = analyze_future_trend([
        dict(observed_at=r["observed"].isoformat(),
             value=r["value"], source=source_name,
             evidence_ref=r["sha"])
        for r in ordered
    ], now=cutoff, freshness_window_days=max(14.,min(intervals)*4))
    cv = _mae_outcomes(ordered, eligible_revisions)
    rising = trend["direction"] == "up"
    falling = trend["direction"] == "down"
    accel = trend["acceleration_per_day"]
    phase = (
        "ACCELERATING_RISE_RESEARCH" if rising and accel > 0
        else "RISING_BUT_SLOWING_RESEARCH" if rising and accel < 0
        else "ACCELERATING_DECLINE_RESEARCH" if falling and accel < 0
        else "DECLINE_SLOWING_RESEARCH" if falling and accel > 0
        else "STABLE_OR_UNRESOLVED_RESEARCH"
    )
    span = (ordered[-1]["observed"]-ordered[0]["observed"]).total_seconds()/86400
    recent_gap = (cutoff-ordered[-1]["observed"]).total_seconds()/86400
    stale = recent_gap > max(14., 2 * max(intervals))
    slope=(ordered[-1]["value"]-ordered[0]["value"])/span
    horizons=[]
    for horizon in HORIZONS:
        justified_horizon = horizon <= min(span, 12*max(intervals))
        can_show = (cv["drift_beats_naive"] is True and not stale
                    and justified_horizon)
        scenario = None
        if can_show:
            scenario = max(0., ordered[-1]["value"]+slope*horizon)
            if unit=="index_0_100":
                scenario=min(100.,scenario)
        horizons.append({
            "days": horizon,
            "directional_scenario_value": round(scenario,6) if scenario is not None else None,
            "scenario_status": (
                "ILLUSTRATIVE_NOT_A_VERIFIED_FORECAST" if can_show
                else "HELD_STALE_OR_UNVALIDATED_OR_EXTRAPOLATION"
            ),
            "prediction_interval": None,
        })
    return {
        **base,
        "status": "OBSERVED_TREND_RESEARCH_ONLY",
        "latest_observed_at": ordered[-1]["observed"].isoformat(),
        "observed_direction": trend["direction"],
        "observed_velocity_per_day": trend["velocity_per_day"],
        "observed_acceleration_per_day": trend["acceleration_per_day"],
        "observed_persistence": trend["persistence"],
        "emerging_or_reversing_trend_phase": phase,
        "phase_is_a_confirmed_causal_or_buyer_demand_signal": False,
        "trend_confidence_is_calibrated_probability": False,
        "rolling_validation_status": cv["validation_status"],
        "rolling_backtest": cv,
        "source_series_stale_at_as_of": stale,
        "future_scenarios": horizons,
        "future_opportunity_status": "RESEARCH_ONLY_NO_VERIFIED_BUYER_DEMAND",
        "scenario_is_predicted_customer_revenue": False,
    }
