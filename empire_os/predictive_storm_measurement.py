"""Source-owned Storm product measurement instrument for Predictive Revenue.

Storm detection is not property damage, verified buying demand, a qualified
contractor, billable revenue, capacity, or a calibrated forecast. Never use
stale snapshots to claim today's weather/market exposure.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.predictive_customer_value_demand import _time

SCHEMA = "empire.predictive_revenue.storm_measurement.v1"
SOURCE_SCHEMA = "empire.storm_opportunity_snapshot.v1"
RUNTIME_SCHEMA = "empire.storm_intelligence_runtime.v1"
SOURCE_REL = "runtime/storm_opportunity/latest.json"
MAX_BYTES = 3_000_000
FRESHNESS = timedelta(hours=24)
COUNTERS = (
    "events_seen", "events_valid", "events_rejected",
    "events_deduplicated", "subjects_considered", "subjects_supported",
    "matches_considered", "assessments_completed", "opportunities_emitted",
    "blocked_count", "evidence_conflict_count",
)
REQUIRED_FALSE = (
    "automatic_external_execution_allowed", "damage_inferred",
    "buyer_intent_inferred", "demand_inferred", "pricing_inferred",
    "economics_inferred",
)
REQUIRED_NONE = (
    "execution_authority", "commercial_authority", "outreach_authority",
    "payment_authority", "revenue_recognition_authority", "traffic_authority",
)


def _result(code: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE", "status": code,
        "source_snapshot_generated_at": None, "source_revision_sha256": None,
        "source_age_hours": None, "storm_event_observation_count": None,
        "source_valid_storm_event_count": None,
        "supported_subject_count": None, "matched_buyer_product_record_count": None,
        "source_opportunity_candidate_count": None,
        "blocked_assessment_count": None,
        "source_diagnostic_counters": None,
        "source_health_claim": None,
        "source_research_usable_for_current_market_simulation": False,
        "actual_storm_damage_verified": False,
        "original_weather_observation_independently_authenticated": False,
        "geographic_property_exposure_verified": False,
        "buyer_demand_or_terms_verified": False,
        "contractor_capacity_or_material_costs_verified": False,
        "storm_opportunity_revenue_verified": False,
        "economic_twin_weather_shock_calibrated": False,
        "original_quant_forecast_registered": False,
        "forecast_outcome_calibration_allowed": False,
        "candidate_payloads_exposed": False,
        "execution_authority": "none", "outbound_sent": False,
        "database_writes": False,
    }


def review_storm_measurement(
    source: Mapping[str, Any] | None, *, as_of: datetime,
) -> dict[str, Any]:
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("trusted aware review time required")
    if source is None:
        return _result("STORM_SOURCE_UNAVAILABLE")
    if (not isinstance(source, Mapping)
            or source.get("schema_version") != SOURCE_SCHEMA
            or source.get("runtime_schema_version") != RUNTIME_SCHEMA
            or source.get("mode") != "OBSERVE"
            or source.get("available") is not True
            or source.get("unknown_stays_unknown") is not True
            or any(source.get(flag) is not False for flag in REQUIRED_FALSE)
            or any(source.get(flag) != "none" for flag in REQUIRED_NONE)):
        return _result("STORM_SOURCE_CONTRACT_HOLD")
    try:
        generated = _time(source.get("generated_at"))
    except ValueError:
        return _result("STORM_SOURCE_CLOCK_HOLD")
    now = as_of.astimezone(timezone.utc)
    age = now-generated
    if age < timedelta(0):
        return _result("STORM_SOURCE_CLOCK_HOLD")
    # Inspect the source contract even if stale. Never return stale event counts
    # as if they described the current forecast or current severe weather.
    diag = source.get("diagnostics")
    candidates = source.get("candidates")
    n = source.get("candidate_count")
    if (not isinstance(diag, Mapping) or not isinstance(candidates, list)
            or type(n) is not int or not 0 <= n <= 10_000
            or len(candidates) != n
            or any(type(diag.get(k)) is not int or not 0 <= diag[k] <= 10_000_000
                   for k in COUNTERS)):
        return _result("STORM_SOURCE_COUNT_HOLD")
    c = {k: diag[k] for k in COUNTERS}
    if (c["events_valid"] > c["events_seen"]
            or c["events_rejected"] > c["events_seen"]
            or c["events_deduplicated"] > c["events_seen"]
            or c["subjects_supported"] > c["subjects_considered"]
            or c["opportunities_emitted"] != n
            or c["opportunities_emitted"] > c["assessments_completed"]
            or c["evidence_conflict_count"] > c["events_seen"]
            or not isinstance(diag.get("source_health"), str)
            or diag["source_health"] not in ("HEALTHY","DEGRADED","UNKNOWN")):
        return _result("STORM_SOURCE_COUNT_HOLD")
    for row in candidates:
        if (not isinstance(row, Mapping)
                or row.get("commercial_ready") is not False
                or row.get("revenue_inferred") is not False
                or row.get("buyer_intent_inferred") is not False
                or row.get("demand_inferred") is not False
                or row.get("pricing_inferred") is not False
                or row.get("economics") is not None
                or any(row.get(k) != "none"
                       for k in ("execution_authority","commercial_authority",
                                 "payment_authority","revenue_recognition_authority",
                                 "outreach_authority"))):
            return _result("STORM_CANDIDATE_AUTHORITY_HOLD")
    if age > FRESHNESS:
        result = _result("STORM_SOURCE_STALE_HOLD")
        result["source_snapshot_generated_at"] = generated.isoformat()
        result["source_age_hours"] = round(age.total_seconds()/3600, 3)
        return result
    if diag["source_health"] != "HEALTHY":
        return _result("STORM_SOURCE_HEALTH_HOLD")
    # A content hash identifies this exact aggregate but doesn't authenticate
    # individual storm observations, property identities or source licences.
    # Source revision covers the full original snapshot, not merely counters.
    # The digest is an anti-drift identifier only; it is not a signed receipt.
    try:
        digest = sha256(json.dumps(
            source, sort_keys=True, separators=(",",":"),allow_nan=False,
        ).encode()).hexdigest()
    except (ValueError, TypeError, RecursionError):
        return _result("STORM_SOURCE_CONTENT_HOLD")
    return {
        **_result("STORM_SOURCE_RESEARCH_MEASURED"),
        "source_snapshot_generated_at": generated.isoformat(),
        "source_revision_sha256": digest,
        "source_age_hours": round(age.total_seconds()/3600, 3),
        "storm_event_observation_count": c["events_seen"],
        "source_valid_storm_event_count": c["events_valid"],
        "supported_subject_count": c["subjects_supported"],
        "matched_buyer_product_record_count": c["matches_considered"],
        "source_opportunity_candidate_count": n,
        "blocked_assessment_count": c["blocked_count"],
        "source_diagnostic_counters": c,
        "source_health_claim": diag["source_health"],
        "source_research_usable_for_current_market_simulation": False,
        # Even a fresh producer snapshot is evidence of producer observations,
        # not of original NWS authenticity, exposed buildings or financial truth.
    }


def review_storm_measurement_runtime(
    repo_root: str | Path, *, as_of: datetime,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    path = root / SOURCE_REL
    try:
        if ((root/"runtime").is_symlink() or path.parent.is_symlink()
                or path.is_symlink() or not path.is_file()
                or not 0 < path.stat().st_size <= MAX_BYTES):
            return _result("STORM_SOURCE_UNAVAILABLE")
        source = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return _result("STORM_SOURCE_UNREADABLE")
    return review_storm_measurement(source, as_of=as_of)
