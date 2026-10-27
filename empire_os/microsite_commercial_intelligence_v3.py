"""Microsite commercial research overlay using ORIGINAL EmpireOS source owners.

- Original Lead Smart coverage reader supplies ZIP-level research guidance only.
- Original Predictive V3 registry format supplies forecasts when exact scoped
  dimensions and the canonical registry payload digest are verified.
- Neither source licenses publishing, buyer activation, routing or revenue claims.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math
import re
from typing import Any, Mapping, Sequence

from empire_os.lead_smart_coverage_reader import load_snapshot, lookup_zip
from empire_os.predictive_cloud_v3 import DirectionalForecast, MIN_FORECAST_SAMPLES
from empire_os.predictive_registry import ForecastRegistryRecord
from empire_os.predictive_microsite_factory import build_candidate

US_ZIP = re.compile(r"[0-9]{5}\Z")
ALLOW_FORECAST_METRICS = frozenset({
    "observed_search_query_impressions",
    "observed_owned_page_clicks",
    "observed_consented_enquiries",
})


def _aware(value: Any) -> datetime:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise ValueError("timestamp must be a datetime or ISO8601")
    if result.tzinfo is None:
        raise ValueError("timezone-aware timestamp required")
    return result.astimezone(timezone.utc)


def read_original_buyer_snapshot(path: Path) -> tuple[dict[str, Any], str]:
    """Original reader validates source semantics; caller owns precise file path."""
    if path.is_symlink() or not path.is_file():
        raise ValueError("buyer snapshot missing or symlink")
    snapshot = load_snapshot(path)
    if (snapshot.get("authority", {}).get("execution_authority") not in
            ("none", "NONE", None)):
        raise ValueError("unexpected buyer coverage authority")
    return snapshot, hashlib.sha256(path.read_bytes()).hexdigest()


def buyer_targeting_observation(
    spec: Mapping[str, Any],
    *,
    snapshot: Mapping[str, Any] | None,
    snapshot_sha256: str | None = None,
    now: datetime,
) -> dict[str, Any]:
    """A buyer row proves targeting guidance only, even with a matched ZIP."""
    now = _aware(now)
    buyer = spec.get("buyer_signal")
    if buyer is None:
        return {
            "status": "BUYER_PATH_UNSPECIFIED",
            "buyer": None, "coverage_observed": None,
            "qualified_payer_verified": False, "live_route_eligible": False,
            "source_sha256": None, "execution_authority": "none",
        }
    if (not isinstance(buyer, Mapping)
            or set(buyer) != {"buyer_key", "service"}
            or buyer.get("buyer_key") != "lead_smart"
            or buyer.get("service") != "roofing"):
        raise ValueError("unsupported buyer signal; exact buyer/service required")
    if snapshot is None:
        return {
            "status": "BUYER_COVERAGE_SOURCE_MISSING",
            "buyer": "Lead Smart", "coverage_observed": None,
            "qualified_payer_verified": False, "live_route_eligible": False,
            "source_sha256": None, "execution_authority": "none",
        }
    if (snapshot.get("schema_version") != "empire.lead_smart.coverage_snapshot.v1"
            or snapshot.get("mode") != "OBSERVE"
            or snapshot.get("source", {}).get("semantics") != "TARGETING_GUIDANCE_ONLY"
            or snapshot.get("source", {}).get("payout_guaranteed") is not False):
        raise ValueError("buyer source has invalid targeting-only semantics")
    geo = spec.get("geography") or {}
    if geo.get("kind") != "us_zip" or not US_ZIP.fullmatch(str(geo.get("area") or "")):
        return {
            "status": "BUYER_ZIP_REQUIRED",
            "buyer": "Lead Smart", "coverage_observed": None,
            "qualified_payer_verified": False, "live_route_eligible": False,
            "source_sha256": snapshot_sha256, "execution_authority": "none",
        }
    observed = lookup_zip(dict(snapshot), str(geo["area"]), now=now)
    if (observed.get("schema_version") != "empire.lead_smart.zip_intelligence.v1"
            or observed.get("payout_guaranteed") is not False
            or observed.get("evidence_class") != "OBSERVED_TARGETING_GUIDANCE"):
        raise ValueError("original buyer lookup contract changed")
    guidance = observed.get("coverage_observed") is True
    fresh = observed["freshness"]["fresh_for_targeting_analysis"] is True
    return {
        "status": ("TARGETING_GUIDANCE_ONLY" if guidance and fresh
                   else "STALE_TARGETING_GUIDANCE" if guidance
                   else "ZIP_NOT_OBSERVED"),
        "buyer": "Lead Smart",
        "vertical": "roofing",
        "zip": geo["area"],
        "coverage_observed": guidance,
        "fresh_for_research": fresh,
        "targeting_candidate": observed["targeting_candidate"] is True,
        # A separate exact-domain/page approval and the original commercial
        # terms/route/consent are required for actual lead acquisition.
        "source_sha256": snapshot_sha256,
        "source_last_updated": observed.get("source_last_updated"),
        "qualifying_buyer_terms_verified_for_this_preview": False,
        "qualified_payer_verified": False,
        "live_route_eligible": False,
        "buyer_accepted_lead": False,
        "payout_guaranteed": False,
        "tracked_accepted_revenue": None,
        "execution_authority": "none",
    }


def forecast_observation(
    spec: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]] | None,
    *,
    now: datetime,
) -> dict[str, Any]:
    """Validate original V3 registry evidence and exact user-supplied binding."""
    now = _aware(now)
    binding = spec.get("predictive_forecast_binding")
    base = {
        "status": "FORECAST_NOT_BOUND",
        "forecast_key": None, "metric": None, "dimension_key": None,
        "model_name": None, "model_version": None,
        "direction": None, "predicted_value": None,
        "evidence_confidence": None, "fresh_for_research": False,
        "verified_forecast_registry_record": False,
        "forecast_is_buyer_or_conversion_proof": False,
        "execution_authority": "none",
    }
    if binding is None:
        return base
    if (not isinstance(binding, Mapping)
            or set(binding) != {"forecast_key", "dimension_key", "metric"}
            or not all(isinstance(v, str) and v.strip() for v in binding.values())
            or binding["metric"] not in ALLOW_FORECAST_METRICS):
        raise ValueError("unsupported or incomplete forecast binding")
    base = dict(base, forecast_key=binding["forecast_key"],
                metric=binding["metric"], dimension_key=binding["dimension_key"])
    if rows is None:
        return dict(base, status="FORECAST_SOURCE_MISSING")
    if not isinstance(rows, (list, tuple)) or len(rows) > 500:
        raise ValueError("forecast registry rows must be bounded")
    matches = [
        r for r in rows if isinstance(r, Mapping)
        and r.get("forecast_key") == binding["forecast_key"]
        and r.get("dimension_key") == binding["dimension_key"]
        and r.get("metric") == binding["metric"]
    ]
    if len(matches) != 1:
        return dict(base, status="FORECAST_AMBIGUOUS" if matches else "FORECAST_NOT_OBSERVED")
    r = matches[0]
    evidence = r.get("evidence")
    if not isinstance(evidence, dict):
        return dict(base, status="FORECAST_PROVENANCE_INVALID")
    digest = evidence.get("registry_payload_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        return dict(base, status="FORECAST_PROVENANCE_INVALID")
    # Do not accept arbitrary keyword-to-location claims. The source must name
    # both the original market and keyword, not simply a similar numeric trend.
    geo = spec.get("geography") or {}
    keyword = (spec.get("keyword_opportunity") or {}).get("keyword")
    if (evidence.get("microsite_market_id") != geo.get("market_id")
            or evidence.get("microsite_area") != geo.get("area")
            or evidence.get("microsite_area_kind") != geo.get("kind")
            or evidence.get("microsite_keyword") != keyword
            or evidence.get("scope_authorized_for_microsite_research") is not True):
        return dict(base, status="FORECAST_SCOPE_NOT_VERIFIED")
    try:
        forecast = DirectionalForecast(
            available=True,
            metric=r["metric"], horizon_days=r["horizon_days"],
            sample_count=r["sample_count"],
            latest_observed_value=r["latest_observed_value"],
            predicted_value=r["predicted_value"],
            daily_slope=r["daily_slope"],
            r_squared=r["r_squared"],
            evidence_confidence=r["evidence_confidence"],
            direction=r["direction"],
            reason=None, source=r["source"],
        )
        record = ForecastRegistryRecord(
            forecast_key=r["forecast_key"],
            model_name=r["model_name"],
            model_version=r["model_version"],
            dimension_key=r["dimension_key"],
            forecast=forecast,
            evidence={k: v for k, v in evidence.items()
                      if k != "registry_payload_sha256"},
        )
        if record.payload_sha256 != digest:
            raise ValueError("tampered forecast hash")
        generated_at = _aware(r["generated_at"])
        predicted = forecast.predicted_value
        confidence = forecast.evidence_confidence
        if (type(forecast.horizon_days) is not int
                or not 1 <= forecast.horizon_days <= 365
                or type(forecast.sample_count) is not int
                or forecast.sample_count < MIN_FORECAST_SAMPLES
                or forecast.metric not in ALLOW_FORECAST_METRICS
                or any(v is None or isinstance(v, bool) or not isinstance(v, (int, float))
                       or not math.isfinite(v) or v < 0
                       for v in (predicted, confidence, forecast.r_squared))
                or confidence > 1 or forecast.r_squared > 1):
            raise ValueError("forecast values invalid")
    except (KeyError, TypeError, ValueError, OverflowError):
        return dict(base, status="FORECAST_PROVENANCE_INVALID")
    age = (now - generated_at).total_seconds()
    if not 0 <= age <= 48 * 3600:
        return dict(base, status="FORECAST_OUTSIDE_FRESHNESS_WINDOW")
    return dict(
        base, status="OBSERVED_PREDICTIVE_RESEARCH_SIGNAL",
        model_name=record.model_name, model_version=record.model_version,
        direction=forecast.direction, predicted_value=predicted,
        evidence_confidence=confidence, horizon_days=forecast.horizon_days,
        generated_at=generated_at.isoformat(), fresh_for_research=True,
        verified_forecast_registry_record=True,
        # No forecast is proof of search volume, a willing payer or revenue.
        forecast_is_buyer_or_conversion_proof=False,
        actual_revenue_verified=False,
    )


def build_microsite_commercial_review(
    specs: Sequence[Mapping[str, Any]], *,
    buyer_snapshot: Mapping[str, Any] | None = None,
    buyer_snapshot_sha256: str | None = None,
    forecast_rows: Sequence[Mapping[str, Any]] | None = None,
    now: datetime,
) -> dict[str, Any]:
    """Overlay independent original evidence without mutating page candidates."""
    if not isinstance(specs, (list, tuple)) or not 1 <= len(specs) <= 25:
        raise ValueError("candidate batch must be 1..25")
    results = []
    for spec in specs:
        packet, _ = build_candidate(spec)
        buyer = buyer_targeting_observation(
            spec, snapshot=buyer_snapshot,
            snapshot_sha256=buyer_snapshot_sha256, now=now)
        forecast = forecast_observation(spec, forecast_rows, now=now)
        reasons = list(packet["blockers"])
        if buyer["status"] not in ("BUYER_PATH_UNSPECIFIED",):
            if buyer["status"] != "TARGETING_GUIDANCE_ONLY":
                reasons.append("buyer ZIP targeting evidence missing/stale")
            reasons.append("no approved buyer route for this exact preview")
        if forecast["status"] != "FORECAST_NOT_BOUND":
            if forecast["status"] != "OBSERVED_PREDICTIVE_RESEARCH_SIGNAL":
                reasons.append(f'forecast source: {forecast["status"]}')
            reasons.append("predictive forecast is research evidence, not verified buyer revenue")
        results.append({
            "candidate_id": packet["id"],
            "area": packet["market"]["area"],
            "keyword": packet["keyword"]["record"]["keyword"],
            "buyer_targeting": buyer,
            "predictive_forecast": forecast,
            "commercial_ready_to_publish": False,
            "automated_domain_spinning_enabled": False,
            "buyer_activation_authorized": False,
            "paid_traffic_authorized": False,
            "enquiry_capture_authorized": False,
            "revenue_verified": False,
            "status": "HOLD_COMMERCIAL_AND_OWNER_REVIEW",
            "reasons": reasons,
        })
    return {
        "schema_version": "empire.microsite_commercial_intelligence.v3",
        "mode": "OBSERVE", "execution_authority": "none",
        "buyer_coverage_source_sha256": buyer_snapshot_sha256,
        "candidates_reviewed": len(results),
        "research_candidates_with_observed_buyer_coverage": sum(
            r["buyer_targeting"]["coverage_observed"] is True for r in results),
        "candidates_with_valid_forecast_records": sum(
            r["predictive_forecast"]["verified_forecast_registry_record"] is True
            for r in results),
        "publishable_candidates": 0,
        "published": False, "database_writes": False, "outbound_sent": False,
        "candidates": results,
    }


def read_original_predictive_registry(
    dsn: str, *,
    limit: int = 100,
    reader: Any = None,
) -> list[dict[str, Any]]:
    """Use the original dedicated Predictive Registry read role, never a writer.

    Source existence, row integrity and exact forecast binding are evaluated
    separately by forecast_observation; query results never grant authority.
    """
    if not isinstance(dsn, str) or not dsn.strip():
        raise ValueError("dedicated predictive registry reader DSN required")
    if type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError("forecast read limit must be 1..500")
    if reader is None:
        from empire_os.predictive_registry_transport import PostgresPredictiveRegistryReader
        reader = PostgresPredictiveRegistryReader(dsn)
    rows = reader(limit=limit)
    if not isinstance(rows, list) or len(rows) > limit:
        raise ValueError("original forecast reader returned invalid batch")
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError("original forecast reader returned malformed row")
    return rows
