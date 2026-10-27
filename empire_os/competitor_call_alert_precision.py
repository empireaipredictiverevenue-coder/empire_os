"""County/forecast-zone NWS evidence for original call-acquisition market research.

One public alert detail per existing opportunity cycle. The NWS CAP geocode
distinguishes C=county UGC from Z=forecast zone; never joins to ZIPs, people,
damaged properties, buyer acceptance, or a campaign.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

import requests

SCHEMA = "empire.competitor_call_alert_precision.v1"
GEO_SCHEMA = "empire.search_fabric.geo_opportunity_observation.v68"
GEO = Path("runtime/search_fabric_evidence/geo_opportunity_latest_v68.json")
DEST = Path("runtime/competitive_intelligence/call_alert_precision_latest.json")
STATE_CODES = frozenset("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split())
UGC = re.compile(r"([A-Z]{2})([CZ])([0-9]{3})")
MAX_INPUT_EVENTS = 100


def _date(raw: Any) -> datetime:
    if not isinstance(raw, str):
        raise ValueError("missing timestamp")
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("naive source clock")
    return dt.astimezone(timezone.utc)


def _official_alert_url(url: Any) -> bool:
    if not isinstance(url, str) or not 30 <= len(url) <= 400:
        return False
    try:
        p = urlsplit(url)
        return (p.scheme == "https" and p.netloc == "api.weather.gov"
                and not p.query and not p.fragment
                and p.path.startswith("/alerts/urn:oid:")
                and re.fullmatch(r"/alerts/urn:oid:[0-9A-Za-z.]+", p.path) is not None)
    except ValueError:
        return False


def _eligible(snapshot: dict, now: datetime) -> list[dict]:
    if (not isinstance(snapshot, dict) or snapshot.get("schema_version") != GEO_SCHEMA
            or snapshot.get("source_url") != "https://api.weather.gov/alerts/active"
            or snapshot.get("source") != "NOAA_NWS_PUBLIC_ALERTS"
            or snapshot.get("source_rights_readonly_public_alerts") is not True
            or snapshot.get("outbound_sent") is not False
            or snapshot.get("database_writes") is not False):
        raise ValueError("untrusted original NWS feed")
    if not 0 <= (now - _date(snapshot.get("retrieved_at_utc"))).total_seconds() <= 7200:
        return []
    original = snapshot.get("geo_events")
    if not isinstance(original, list) or len(original) > MAX_INPUT_EVENTS:
        raise ValueError("unbounded original NWS feed")
    grouped: dict[str, dict] = {}
    for e in original:
        if not isinstance(e, dict):
            raise ValueError("invalid NWS event")
        if "roofing" not in e.get("potential_supply_research_verticals", []):
            continue
        url = e.get("source_record_url")
        digest = e.get("source_event_sha256")
        if not _official_alert_url(url) or digest != hashlib.sha256(url.encode()).hexdigest():
            raise ValueError("NWS alert ID integrity failed")
        if e.get("geographic_precision") != "NWS_UGC_STATE_ONLY_NOT_ADDRESS_OR_ZIP":
            raise ValueError("state-only NWS input required")
        state = e.get("state")
        if state not in STATE_CODES:
            raise ValueError("invalid original source state")
        if not _date(e.get("issued_at_utc")) <= now < _date(e.get("expires_at_utc")):
            continue
        if url not in grouped:
            grouped[url] = {
                "url": url, "sha256": digest, "event": e.get("event"),
                "source_states": set(), "issued_at_utc": e["issued_at_utc"],
                "expires_at_utc": e["expires_at_utc"],
            }
        if grouped[url]["event"] != e.get("event"):
            raise ValueError("same NWS source has conflicting labels")
        grouped[url]["source_states"].add(state)
    return [
        {**e, "source_states": sorted(e["source_states"])}
        for _, e in sorted(grouped.items())
    ]


def fetch_official_alert(url: str) -> dict | None:
    if not _official_alert_url(url):
        return None
    try:
        with requests.get(
            url, headers={
                "User-Agent": "EmpireOS-Call-Research/1.0 (+https://empire-ai.co.uk)",
                "Accept": "application/geo+json",
            }, timeout=8, allow_redirects=False, stream=True,
        ) as r:
            if r.status_code != 200 or "json" not in r.headers.get("Content-Type", "").lower():
                return None
            body = bytearray()
            for chunk in r.iter_content(chunk_size=16384):
                body.extend(chunk)
                if len(body) > 100_000:
                    return None
        data = json.loads(body)
        return data if isinstance(data, dict) else None
    except (requests.RequestException, ValueError, TypeError):
        return None


def parse_official_alert(record: dict, data: dict, *, now: datetime) -> dict:
    """Only explicitly present county UGCs are counted as county-area codes."""
    if not isinstance(data, dict) or data.get("type") != "Feature":
        raise ValueError("not a NWS GeoJSON feature")
    props = data.get("properties")
    if not isinstance(props, dict):
        raise ValueError("NWS response missing properties")
    url = record["url"]
    if (props.get("@id") != url or data.get("id") != url
            or props.get("event") != record["event"]
            or props.get("status") != "Actual"
            or props.get("messageType") in ("Cancel", "Error")):
        raise ValueError("NWS source identity/event/status mismatch")
    sent = _date(props.get("sent"))
    expiry = _date(props.get("ends") or props.get("expires"))
    if not sent <= now < expiry:
        raise ValueError("no longer active official alert")
    if abs((sent - _date(record["issued_at_utc"])).total_seconds()) > 60:
        raise ValueError("NWS original/official issue timestamps differ")
    geocodes = props.get("geocode")
    if not isinstance(geocodes, dict) or not isinstance(geocodes.get("UGC"), list):
        raise ValueError("missing NWS UGCs")
    zones = geocodes["UGC"]
    if not 1 <= len(zones) <= 200:
        raise ValueError("unexpected NWS UGC area count")
    counties, forecasts = set(), set()
    for item in zones:
        if not isinstance(item, str) or not UGC.fullmatch(item) or item[:2] not in STATE_CODES:
            raise ValueError("invalid official NWS UGC identifier")
        if item[2] == "C":
            counties.add(item)
        else:
            forecasts.add(item)
    original_states = set(record["source_states"])
    area_states = {c[:2] for c in counties | forecasts}
    if not original_states.issubset(area_states):
        raise ValueError("official detail does not contain original source state")
    affected = props.get("affectedZones")
    if not isinstance(affected, list) or len(affected) > 200:
        raise ValueError("missing linked zone list")
    # Official affectedZones can omit or partition some UGC entries; preserve
    # geocode UGC's exact typed scope, never imply official county polygons.
    return {
        "source_url": url, "source_sha256": record["sha256"],
        "event_type": props["event"],
        "source_states": sorted(original_states),
        "official_ugc_states": sorted(area_states),
        "official_county_ugc_ids": sorted(counties),
        "official_forecast_zone_ugc_ids": sorted(forecasts),
        "county_ugc_count": len(counties),
        "forecast_zone_ugc_count": len(forecasts),
        "geographic_precision": (
            "NWS_COUNTY_UGC_IDENTIFIERS_AND_FORECAST_ZONES"
            if counties and forecasts else
            "NWS_COUNTY_UGC_IDENTIFIERS_ONLY" if counties else
            "NWS_FORECAST_ZONE_IDENTIFIERS_ONLY"
        ),
        "issued_at_utc": sent.isoformat(),
        "expires_at_utc": expiry.isoformat(),
        "observed_at_utc": now.isoformat(),
        "affected_zones_metadata_only": len(affected),
        "county_name_or_geometry_verified": False,
        "county_fips_crosswalk_verified": False,
        "affected_property_zip_codes_verified": False,
        "homeowner_need_verified": False,
        "buyer_capacity_or_acceptance_verified": False,
    }


def review_once(
    snapshot: dict, previous: dict | None = None, *, now: datetime | None = None,
    fetch: Callable[[str], dict | None] = fetch_official_alert,
) -> dict:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("timezone-aware time required")
    now = now.astimezone(timezone.utc)
    events = _eligible(snapshot, now)
    previous = previous if isinstance(previous, dict) and previous.get("schema_version") == SCHEMA else {}
    cursor = previous.get("cursor") if type(previous.get("cursor")) is int else 0
    cursor = max(0, cursor)
    index = cursor % len(events) if events else 0
    selected = events[index] if events else None
    observations = {
        r["source_url"]: r for r in (previous.get("observations") or [])
        if isinstance(r, dict) and r.get("source_url")
        and r.get("source_url") in {x["url"] for x in events}
        and _date(r.get("expires_at_utc")) > now
    }
    last_fetch = "NO_ACTIVE_ROOFING_EVENTS_OR_STALE_SOURCE"
    if selected is not None:
        try:
            response = fetch(selected["url"])
            row = parse_official_alert(selected, response, now=now) if response else None
        except (ValueError, TypeError, KeyError):
            row = None
        if row:
            observations[selected["url"]] = row
            last_fetch = "VERIFIED_OFFICIAL_ALERT_DETAIL"
        else:
            last_fetch = "DETAIL_FETCH_UNAVAILABLE_OR_UNVERIFIED"
    ordered = sorted(observations.values(), key=lambda x: x["source_url"])
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "generated_at": now.isoformat(),
        "source": "EXISTING_GEO_V68_PLUS_OFFICIAL_NWS_DETAIL",
        "original_source_retrieved_at": snapshot.get("retrieved_at_utc"),
        "eligible_roofing_event_count": len(events),
        "detail_checked_this_cycle": 1 if selected is not None else 0,
        "last_checked_source_url": selected["url"] if selected else None,
        "last_fetch_status": last_fetch,
        "cursor": (index + 1) if selected else 0,
        "observations": ordered[:30],
        "official_detail_observation_count": len(ordered[:30]),
        "county_ugc_area_count": sum(x["county_ugc_count"] for x in ordered[:30]),
        "forecast_zone_area_count": sum(x["forecast_zone_ugc_count"] for x in ordered[:30]),
        "evidence_has_no_zip_or_property_mapping": True,
        "county_fips_crosswalk_verified": False,
        "roof_damage_or_customer_intent_inferred": False,
        "accepted_buyer_territory_verified": False,
        "outreach_enabled": False,
        "call_activation_authorized": False,
        "execution_authority": "none",
    }


def refresh(root: Path) -> dict:
    snapshot = json.loads((root / GEO).read_text(encoding="utf-8"))
    dst = root / DEST
    if not dst.parent.is_dir() or dst.parent.is_symlink() or dst.is_symlink():
        raise ValueError("unsafe original runtime destination")
    try:
        previous = json.loads(dst.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = None
    # NOAA advises against rapid repeat requests. Preserve the prior verified
    # receipt rather than hitting their public API twice within 45 seconds.
    if isinstance(previous, dict) and previous.get("schema_version") == SCHEMA:
        try:
            elapsed = (datetime.now(timezone.utc) -
                       _date(previous.get("generated_at"))).total_seconds()
        except (TypeError, ValueError):
            elapsed = -1
        if 0 <= elapsed < 45:
            return previous
    report = review_once(snapshot, previous)
    fd, tmp = tempfile.mkstemp(prefix=".alert-precision-", dir=dst.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as h:
            json.dump(report, h, indent=2, sort_keys=True)
            h.write("\n")
            h.flush()
            os.fsync(h.fileno())
        os.replace(tmp, dst)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return report
