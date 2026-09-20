#!/usr/bin/env python3
"""Bounded OpenStreetMap/Overpass business-identity source."""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from typing import Iterator, Optional

from empire_os.lead_sources import LeadCandidate, SourceInfo


METRO_COORDS = {
    "Houston, TX": (29.763284, -95.363271),
    "Dallas, TX": (32.776672, -96.796888),
    "Austin, TX": (30.267153, -97.743057),
    "San Antonio, TX": (29.424122, -98.493628),
    "Phoenix, AZ": (33.448376, -112.074036),
    "Chicago, IL": (41.878113, -87.629799),
    "Atlanta, GA": (33.749001, -84.387978),
    "Miami, FL": (25.761680, -80.191790),
    "Denver, CO": (39.739235, -104.990250),
    "Los Angeles, CA": (34.052235, -118.243683),
    "New York, NY": (40.712776, -74.005974),
    "Seattle, WA": (47.606209, -122.332069),
    "Charlotte, NC": (35.227087, -80.843127),
    "Nashville, TN": (36.162664, -86.781602),
    "Tampa, FL": (27.950575, -82.457177),
}

CRAFT_TO_NICHE = {
    "roofer": "roofing",
    "hvac": "hvac",
    "plumber": "plumbing",
    "electrician": "electrical",
    "painter": "painting",
    "gardener": "landscaping",
    "carpenter": "carpentry",
    "pest_control": "pest_control",
}

OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
)

RADIUS_M = 25000
FALLBACK_RADII_M = (12000, 6000)
MAX_RESULTS = 200
QUERY_TIMEOUT_SECONDS = 25
NETWORK_TIMEOUT_SECONDS = 35


def _query(lat: float, lon: float, radius: int = RADIUS_M) -> str:
    values = "|".join(
        re.escape(value)
        for value in CRAFT_TO_NICHE
    )
    selector = f'["craft"~"^({values})$"]'

    return f"""
[out:json][timeout:{QUERY_TIMEOUT_SECONDS}];
(
  node{selector}(around:{radius},{lat},{lon});
  way{selector}(around:{radius},{lat},{lon});
  relation{selector}(around:{radius},{lat},{lon});
);
out center {MAX_RESULTS};
""".strip()


def _request_overpass(query: str) -> dict:
    payload = urllib.parse.urlencode(
        {"data": query}
    ).encode()

    last_error = None

    for endpoint in OVERPASS_ENDPOINTS:
        try:
            request = urllib.request.Request(
                endpoint,
                data=payload,
                headers={
                    "User-Agent": (
                        "EmpireOS-BusinessDiscovery/1.0 "
                        "(contact@empire-ai.co.uk)"
                    )
                },
            )

            raw = urllib.request.urlopen(
                request,
                timeout=NETWORK_TIMEOUT_SECONDS,
            ).read().decode("utf-8", "ignore")

            data = json.loads(raw)

            if isinstance(data, dict):
                return data

        except Exception as exc:
            last_error = exc

    if last_error:
        raise RuntimeError(
            "all Overpass endpoints failed: "
            f"{type(last_error).__name__}: {last_error}"
        )

    raise RuntimeError("all Overpass endpoints returned invalid payloads")


def _contact_value(tags: dict, *keys: str) -> str:
    for key in keys:
        value = str(tags.get(key) or "").strip()
        if value:
            return value
    return ""


def _element_to_candidate(element: dict) -> LeadCandidate | None:
    tags = element.get("tags") or {}

    craft = str(
        tags.get("craft") or ""
    ).strip().casefold()

    niche = CRAFT_TO_NICHE.get(craft)
    if not niche:
        return None

    name = str(tags.get("name") or "").strip()
    if not name:
        return None

    phone = _contact_value(
        tags,
        "phone",
        "contact:phone",
        "mobile",
        "contact:mobile",
    )
    website = _contact_value(
        tags,
        "website",
        "contact:website",
    )
    email = _contact_value(
        tags,
        "email",
        "contact:email",
    )

    if not phone and not website and not email:
        return None

    osm_type = str(
        element.get("type") or ""
    ).strip()
    osm_id = element.get("id")

    if osm_type not in {"node", "way", "relation"}:
        return None
    if osm_id in (None, ""):
        return None

    center = element.get("center") or {}
    lat = element.get("lat")
    lon = element.get("lon")

    if lat is None:
        lat = center.get("lat")
    if lon is None:
        lon = center.get("lon")

    number = str(
        tags.get("addr:housenumber") or ""
    ).strip()
    street = str(
        tags.get("addr:street") or ""
    ).strip()
    city = str(
        tags.get("addr:city") or ""
    ).strip()
    state = str(
        tags.get("addr:state") or ""
    ).strip()
    postcode = str(
        tags.get("addr:postcode") or ""
    ).strip()

    street_address = " ".join(
        part for part in (number, street) if part
    )

    address = ", ".join(
        part
        for part in (
            street_address,
            city,
            state,
            postcode,
        )
        if part
    )

    osm_url = (
        f"https://www.openstreetmap.org/"
        f"{osm_type}/{osm_id}"
    )

    score = 60
    score += 15 if phone else 0
    score += 15 if website else 0
    score += 5 if email else 0
    score += 5 if address else 0
    score = min(score, 100)

    details = [
        f"OSM verified trade tag craft={craft}",
        f"OSM object {osm_type}/{osm_id}",
    ]

    if phone:
        details.append(f"Phone {phone}")
    if website:
        details.append(f"Website {website}")
    if email:
        details.append(f"Email {email}")
    if address:
        details.append(f"Address {address}")
    if lat is not None and lon is not None:
        details.append(f"Geo {lat},{lon}")

    return LeadCandidate(
        name=name,
        email=email,
        phone=phone,
        niche=niche,
        metro="",
        state=state,
        details=". ".join(details),
        source="overpass_osm",
        lead_score=score,
        url=osm_url,
        raw={
            "osm_type": osm_type,
            "osm_id": osm_id,
            "lat": lat,
            "lon": lon,
            "craft": craft,
            "business_website": website,
            "osm_tags": tags,
        },
    )


def _fetch(
    lat: float,
    lon: float,
    radius: int = RADIUS_M,
    limit: int = MAX_RESULTS,
) -> list[LeadCandidate]:
    radii = [radius]
    radii.extend(
        value for value in FALLBACK_RADII_M
        if value < radius and value not in radii
    )
    last_error: Exception | None = None
    data = None
    for query_radius in radii:
        try:
            data = _request_overpass(
                _query(lat, lon, query_radius)
            )
            break
        except RuntimeError as exc:
            last_error = exc

    if data is None:
        raise RuntimeError(
            "Overpass failed at all bounded radii"
        ) from last_error

    results = []

    for element in data.get("elements", []):
        candidate = _element_to_candidate(element)

        if candidate is None:
            continue

        results.append(candidate)

        if len(results) >= limit:
            break

    return results


def run(
    metro: Optional[str] = None,
) -> Iterator[LeadCandidate]:

    if metro is not None:
        if metro not in METRO_COORDS:
            return

        targets = {
            metro: METRO_COORDS[metro]
        }
    else:
        targets = METRO_COORDS

    failures = 0

    for metro_name, (lat, lon) in targets.items():
        try:
            for candidate in _fetch(lat, lon):
                candidate.metro = metro_name
                yield candidate
        except Exception as exc:
            failures += 1
            print(
                f"[overpass] metro {metro_name} failed: {exc}"
            )

        time.sleep(1.0)

    if failures == len(targets):
        raise RuntimeError("all requested Overpass metro queries failed")


def register_source(reg):
    reg(
        SourceInfo(
            name="overpass",
            tier="real",
            requires=[],
            description=(
                "OpenStreetMap/Overpass contactable "
                "local trade businesses"
            ),
            run_fn=run,
        )
    )
