"""Official NWS alert zone coverage fallback, NOT a weather-impact footprint.

When NWS publishes an active advisory without inline polygon geometry,
its affectedZones link identifies a coarse official forecast/county zone.
Show that coverage boundary separately, with explicit truth labels.
Only verified HTTPS NWS zone documents matching the alert's referenced URL
are eligible. No business/property/lead geocoding or commercial inference.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping

from empire_os.gods_eye_nws_geojson import MAX_AGE, MAX_FEATURES, _geometry, _time

ZONE_PREFIXES = (
    "https://api.weather.gov/zones/forecast/",
    "https://api.weather.gov/zones/county/",
)
MAX_ZONE_DOCUMENTS = 24
MAX_ZONE_REFERENCES_PER_ALERT = 15


def _zone_link(raw: Any) -> bool:
    if not isinstance(raw, str) or len(raw) > 115:
        return False
    for prefix in ZONE_PREFIXES:
        if raw.startswith(prefix):
            ident = raw[len(prefix):]
            return 3 <= len(ident) <= 15 and ident.isascii() and ident.isalnum()
    return False


def build_nws_advisory_zone_review(
    alerts: Mapping[str, Any],
    verified_zones: Mapping[str, Mapping[str, Any]],
    *,
    now: datetime,
    alerts_transport_verified: bool,
    zone_transports_verified: bool,
) -> dict[str, Any]:
    if now.utcoffset() is None:
        raise ValueError("timezone_aware_clock_required")
    now = now.astimezone(timezone.utc)
    if not (alerts_transport_verified and zone_transports_verified):
        raise ValueError("separate_official_nws_transports_required")
    if (not isinstance(alerts, Mapping) or alerts.get("type") != "FeatureCollection"
            or not isinstance(alerts.get("features"), list)
            or len(alerts["features"]) > 2000):
        raise ValueError("alerts_not_bounded_featurecollection")
    if not isinstance(verified_zones, Mapping) or len(verified_zones) > MAX_ZONE_DOCUMENTS:
        raise ValueError("zone_source_count_invalid")

    features = []
    audit = {
        "alerts_considered": 0,
        "alerts_valid_without_geometry": 0,
        "zones_seen": 0,
        "zones_accepted": 0,
        "zones_unavailable_or_invalid": 0,
        "stale_or_inactive_alerts": 0,
    }
    seen = set()
    for alert in alerts["features"][:200]:
        audit["alerts_considered"] += 1
        if not isinstance(alert, Mapping) or alert.get("type") != "Feature":
            continue
        alert_ref = alert.get("id")
        props = alert.get("properties")
        if (not isinstance(alert_ref, str) or not alert_ref.startswith("https://api.weather.gov/alerts/")
                or not isinstance(props, Mapping)):
            continue
        sent, ends = _time(props.get("sent")), _time(props.get("expires"))
        if (sent is None or ends is None or sent > now or ends <= now
                or now-sent > MAX_AGE or props.get("status") != "Actual"):
            audit["stale_or_inactive_alerts"] += 1
            continue
        # Zones are a fallback when NWS did not supply a true event polygon.
        if _geometry(alert.get("geometry")) is not None:
            continue
        severity, event = props.get("severity"), props.get("event")
        if (not isinstance(event, str) or not 1 <= len(event) <= 90
                or not isinstance(severity, str) or len(severity) > 50):
            continue
        urls = props.get("affectedZones")
        if not isinstance(urls, list) or len(urls) > MAX_ZONE_REFERENCES_PER_ALERT:
            continue
        audit["alerts_valid_without_geometry"] += 1
        for link in urls:
            audit["zones_seen"] += 1
            if not _zone_link(link):
                audit["zones_unavailable_or_invalid"] += 1
                continue
            zone = verified_zones.get(link)
            if (not isinstance(zone, Mapping)
                    or zone.get("type") != "Feature"
                    or zone.get("id") != link
                    or not isinstance(zone.get("properties"), Mapping)
                    or not isinstance(zone["properties"].get("id"), str)
                    or link.rsplit("/", 1)[-1] != zone["properties"]["id"]):
                audit["zones_unavailable_or_invalid"] += 1
                continue
            shape = _geometry(zone.get("geometry"))
            if shape is None:
                audit["zones_unavailable_or_invalid"] += 1
                continue
            key = (alert_ref, link)
            if key in seen:
                continue
            seen.add(key)
            feature_id = "nws-zone:" + sha256((alert_ref+"|"+link).encode()).hexdigest()[:24]
            features.append({
                "type": "Feature", "id": feature_id,
                "geometry": shape,
                "properties": {
                    "event": event,
                    "severity": severity,
                    "alert_ref": alert_ref,
                    "zone_ref": link,
                    "zone_id": zone["properties"]["id"],
                    "zone_name": str(zone["properties"].get("name") or "")[:100],
                    "sent": sent.isoformat(),
                    "expires": ends.isoformat(),
                    "data_owner": "NOAA/NWS",
                    "source_rights": "US_PUBLIC_DATA_WITH_ATTRIBUTION",
                    "geometry_truth": "ADVISORY_FORECAST_ZONE_COVERAGE_NOT_EVENT_FOOTPRINT",
                    "weather_impact_footprint_verified": False,
                    "property_damage_verified": False,
                    "buyer_intent_verified": False,
                    "commercial_opportunity_verified": False,
                    "outreach_authorized": False,
                    "execution_authority": "none",
                },
            })
            audit["zones_accepted"] += 1
            if len(features) >= MAX_FEATURES:
                break
        if len(features) >= MAX_FEATURES:
            break
    return {
        "type": "FeatureCollection",
        "name": "EmpireOS NWS Advisory Zone Coverage - NOT Impact Footprints",
        "features": features,
        "empire_review": {
            "schema_version": "empire.godseye.nws_zone_coverage.v1",
            "generated_at": now.isoformat(),
            "mode": "OBSERVE",
            "official_source": "https://api.weather.gov/alerts/active",
            "source_rights": "NOAA/National Weather Service U.S. public data; no endorsement",
            "geometry_truth": "FORECAST_ZONE_COVERAGE_ONLY",
            "audit": audit,
            "status": "OFFICIAL_ZONE_COVERAGE_AVAILABLE" if features else "NO_CURRENT_VERIFIED_ZONE_COVERAGE",
            "map_layer_tested_in_gods_eye_ui": False,
            "commercial_authority": "none",
            "public_publish_authorized": False,
            "revenue_verified": False,
            "execution_authority": "none",
        },
    }
