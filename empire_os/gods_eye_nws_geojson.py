"""God's Eye-compatible GeoJSON from *dated official* NWS alert geometry.

Read-only spatial presentation contract. Does not infer damage, prospects,
location of a business, property exposure, buyer intent, pricing or revenue.
No external fetcher, database, daemon, public API or new scheduler.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from math import isfinite
from typing import Any, Mapping

SCHEMA = "empire.godseye.nws_spatial_review.v1"
MAX_FEATURES = 50
MAX_VERTICES = 3500
MAX_AGE = timedelta(hours=24)


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 48:
        return None
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d.astimezone(timezone.utc) if d.tzinfo is not None else None


def _ring(value: Any) -> list[list[float]] | None:
    if not isinstance(value, list) or len(value) < 4 or len(value) > MAX_VERTICES:
        return None
    points = []
    for raw in value:
        if not isinstance(raw, list) or len(raw) != 2:
            return None
        x, y = raw
        if (type(x) not in (int, float) or type(y) not in (int, float)
                or not isfinite(x) or not isfinite(y) or not -180 <= x <= 180
                or not -90 <= y <= 90):
            return None
        points.append([float(x), float(y)])
    return points if points[0] == points[-1] else None


def _geometry(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping) or value.get("type") not in ("Polygon", "MultiPolygon"):
        return None
    typ = value["type"]
    raw = value.get("coordinates")
    if not isinstance(raw, list) or not raw or len(raw) > 25:
        return None
    polygons = [raw] if typ == "Polygon" else raw
    clean = []
    total = 0
    for polygon in polygons:
        if not isinstance(polygon, list) or not polygon or len(polygon) > 30:
            return None
        rings = []
        for ring in polygon:
            accepted = _ring(ring)
            if accepted is None:
                return None
            total += len(accepted)
            if total > MAX_VERTICES:
                return None
            rings.append(accepted)
        clean.append(rings)
    return {"type": typ, "coordinates": clean[0] if typ == "Polygon" else clean}


def build_official_nws_review_layer(
    report: Mapping[str, Any], *, now: datetime,
    verified_official_transport: bool = False,
) -> dict[str, Any]:
    """Only officially transported, fresh, geographic NWS polygons are plotted."""
    if now.utcoffset() is None:
        raise ValueError("utc_review_clock_required")
    now = now.astimezone(timezone.utc)
    if not verified_official_transport:
        raise ValueError("original_nws_transport_verification_required")
    if (not isinstance(report, Mapping) or report.get("type") != "FeatureCollection"
            or not isinstance(report.get("features"), list)
            or len(report["features"]) > 2000):
        raise ValueError("nws_geojson_shape_invalid")
    out = []
    counts = {"considered": 0, "geometry_unavailable": 0,
              "stale_or_inactive": 0, "invalid": 0, "accepted": 0}
    for row in report["features"][:200]:
        counts["considered"] += 1
        if not isinstance(row, Mapping) or row.get("type") != "Feature":
            counts["invalid"] += 1
            continue
        props = row.get("properties")
        if not isinstance(props, Mapping):
            counts["invalid"] += 1
            continue
        source = row.get("id")
        if (not isinstance(source, str) or not source.startswith("https://api.weather.gov/alerts/")
                or len(source) > 450):
            counts["invalid"] += 1
            continue
        at = _time(props.get("sent"))
        end = _time(props.get("expires"))
        if (at is None or end is None or at > now or end <= now
                or now - at > MAX_AGE or props.get("status") != "Actual"):
            counts["stale_or_inactive"] += 1
            continue
        geom = _geometry(row.get("geometry"))
        if geom is None:
            counts["geometry_unavailable"] += 1
            continue
        event = props.get("event")
        severity = props.get("severity")
        if (not isinstance(event, str) or not 1 <= len(event) <= 90
                or not isinstance(severity, str) or len(severity) > 50):
            counts["invalid"] += 1
            continue
        fingerprint = hashlib.sha256(source.encode()).hexdigest()[:24]
        out.append({
            "type": "Feature", "id": "nws:" + fingerprint, "geometry": geom,
            "properties": {
                "source_ref": source,
                "data_owner": "NOAA / National Weather Service",
                "source_rights": "US_PUBLIC_DATA_WITH_NWS_DISCLAIMER",
                "observed_at": at.isoformat(),
                "valid_until": end.isoformat(),
                "event": event,
                "severity": severity,
                "source_transport_verified": True,
                "geometry_truth": "OBSERVED_PROVIDER_POLYGON",
                "property_damage_verified": False,
                "buyer_intent_verified": False,
                "commercial_opportunity_verified": False,
                "execution_authority": "none",
            },
        })
        counts["accepted"] += 1
        if len(out) >= MAX_FEATURES:
            break
    return {
        "type": "FeatureCollection",
        "name": "EmpireOS — NWS Observed Alert Polygons",
        "features": out,
        "empire_review": {
            "schema_version": SCHEMA,
            "generated_at": now.isoformat(),
            "mode": "OBSERVE",
            "provider": "NOAA/NWS",
            "attribution": "NOAA/National Weather Service; U.S. public data; no endorsement",
            "official_source": "https://api.weather.gov/alerts/active",
            "max_source_issue_age_hours": 24,
            "counts": counts,
            "status": "GEOJSON_OBSERVATIONS_AVAILABLE" if out else "NO_VERIFIED_CURRENT_POLYGON_GEOMETRY",
            "source_rights_review_required_before_public_commercial_release": True,
            "public_publish_authorized": False,
            "revenue_claims_authorized": False,
            "execution_authority": "none",
        },
    }
