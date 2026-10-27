#!/usr/bin/env python3
"""Live, bounded NWS alert-zone review for a future God's Eye GeoJSON layer.

No publish, business geocoding, scraping, Lead Smart actions or new services.
Only official NOAA endpoints. Zone boundaries are NOT hazard footprints.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
from urllib.request import Request, urlopen

from empire_os.gods_eye_nws_geojson import _time, _geometry, MAX_AGE
from empire_os.gods_eye_nws_zones import _zone_link, build_nws_advisory_zone_review

ALERTS = "https://api.weather.gov/alerts/active?area=TX"
MAX_ALERTS = 2_000_000
MAX_ZONE_BYTES = 950_000
MAX_ZONE_FETCH = 12
HEADERS = {
    "Accept": "application/geo+json",
    "User-Agent": "EmpireAI-spatial-review/1.0 (contact@empire-ai.co.uk)",
}


def _get(url: str, cap: int) -> dict:
    if not url.startswith("https://api.weather.gov/"):
        raise ValueError("unapproved_nws_host")
    with urlopen(Request(url, headers=HEADERS), timeout=13) as result:
        if result.status != 200 or result.geturl() != url:
            raise ValueError("official_nws_request_redirect_or_error")
        data = result.read(cap + 1)
        if len(data) > cap:
            raise ValueError("source_exceeds_bounded_limit")
    value = json.loads(data)
    if not isinstance(value, dict):
        raise ValueError("source_not_json_object")
    return value


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--review-dir", required=True, type=Path)
    args = cli.parse_args(argv)
    if not args.review_dir.is_absolute() or args.review_dir.is_symlink():
        cli.error("absolute_review_dir_required")
    now = datetime.now(timezone.utc)
    document = _get(ALERTS, MAX_ALERTS)
    urls = []
    seen = set()
    for alert in document.get("features", [])[:200]:
        if not isinstance(alert, dict):
            continue
        props = alert.get("properties")
        if not isinstance(props, dict):
            continue
        issued, expires = _time(props.get("sent")), _time(props.get("expires"))
        if (issued is None or expires is None or issued > now or expires <= now
                or now - issued > MAX_AGE
                or props.get("status") != "Actual"
                or _geometry(alert.get("geometry")) is not None):
            continue
        for ref in (props.get("affectedZones") or [])[:15]:
            if _zone_link(ref) and ref not in seen:
                seen.add(ref)
                urls.append(ref)
    responses = {}
    failed = {}
    for url in urls[:MAX_ZONE_FETCH]:
        try:
            responses[url] = _get(url, MAX_ZONE_BYTES)
        except (ValueError, OSError, TimeoutError, json.JSONDecodeError) as exc:
            failed[url] = type(exc).__name__
    reviewed = build_nws_advisory_zone_review(
        document, responses, now=datetime.now(timezone.utc),
        alerts_transport_verified=True, zone_transports_verified=True,
    )
    outdir = args.review_dir
    outdir.mkdir(parents=True, exist_ok=True)
    target = outdir / "nws_advisory_coverage_review.geojson"
    if target.is_symlink() or target.parent.is_symlink():
        raise ValueError("unsafe_review_output_path")
    target.write_text(json.dumps(reviewed, indent=2, sort_keys=True) + "\n")
    summary = {
        "state": reviewed["empire_review"]["status"],
        "generated_at": reviewed["empire_review"]["generated_at"],
        "official_alerts_observed": len(document.get("features", [])),
        "official_zone_sources_requested": min(len(urls), MAX_ZONE_FETCH),
        "official_zone_sources_obtained": len(responses),
        "official_zone_request_failures": failed,
        "geolocated_advisory_zones": len(reviewed["features"]),
        "zone_geometry_truth": "ADVISORY_COVERAGE_NOT_EVENT_FOOTPRINT",
        "actual_damage_or_buyer_intent_verified": False,
        "public_publish_authorized": False,
        "view_rendered_in_upstream_gods_eye": False,
        "review_file": str(target),
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
