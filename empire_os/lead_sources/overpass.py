#!/usr/bin/env python3
"""
Empire OS v3 — Overpass (OpenStreetMap) local-lead source
==========================================================

Keyless, free, unlimited local-business sourcing via the Overpass API.
No API key. Returns real businesses (name / phone / website / geo) within a
radius of a city center — the geo-radius complement to the keyword-based
search-API sources we already run.

Why this exists (per founder decision 2026-07-18):
  - Fill the geo-radius gap for local pay-per-call verticals (roofing, HVAC,
    plumbing, etc.) without depending on a search-API keyword match.
  - 100% legit: public OSM data, no personal-contact scraping, no Origami-style
    individual cell/email harvesting. Business listings only.

Usage:
  from empire_os.lead_sources.overpass import run, register_source
  for lead in run(metro="Houston, TX"):
      intake(lead.to_intake_payload())

Register with the fleet via register_source(reg).
"""
from itertools import islice
from typing import Iterator, Optional
import urllib.request
import urllib.parse
import json
import time

from empire_os.lead_sources import LeadCandidate, SourceInfo, infer_niche

# Major US metro centers (lat, lon). Add more as coverage grows.
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

# OSM amenity/shop/craft tags that map to our pay-per-call verticals.
OSM_TAGS = [
    '"roofing"', '"hvac"', '"plumber"', '"electrician"',
    '"painter"', '"general_contractor"', '"pest_control"',
    '"landscaper"', '"tree_service"', '"mold_remediation"',
    '"disaster_recovery"', '"cleaning"', '"gardener"',
]

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
RADIUS_M = 25000  # 25km radius — covers a metro's suburbs


def _query(lat, lon, radius, tags):
    tag_expr = "][".join(tags)
    return f"""
    [out:json][timeout:25];
    (
      node[{tag_expr}](around:{radius},{lat},{lon});
      way[{tag_expr}](around:{radius},{lat},{lon});
    );
    out center 200;
    """


def _fetch(lat, lon, radius=RADIUS_M, tags=OSM_TAGS, limit=200):
    q = _query(lat, lon, radius, tags)
    try:
        req = urllib.request.Request(
            OVERPASS_URL,
            data=urllib.parse.urlencode({"data": q}).encode(),
            headers={"User-Agent": "EmpireOS-LeadSource/1.0"},
        )
        raw = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
        data = json.loads(raw)
    except Exception as e:
        print(f"[overpass] fetch failed: {e}")
        return []
    out = []
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        # way elements carry center lat/lon
        lat_ = el.get("lat") or el.get("center", {}).get("lat")
        lon_ = el.get("lon") or el.get("center", {}).get("lon")
        name = tags.get("name", "")
        if not name:
            continue
        phone = (tags.get("phone") or tags.get("contact:phone")
                 or tags.get("mobile") or "")
        website = tags.get("website") or tags.get("contact:website") or ""
        # infer niche from the OSM tag that matched
        matched_tag = next((t for t in OSM_TAGS
                            if t.strip('"') in tags), "")
        niche = infer_niche(name + " " + matched_tag.replace('_', ' ')) \
            if matched_tag else infer_niche(name)
        city = tags.get("addr:city", "")
        state = tags.get("addr:state", "")
        street = tags.get("addr:street", "")
        addr = f"{street}, {city}, {state}".strip(", ")
        out.append(LeadCandidate(
            name=name,
            phone=phone,
            niche=niche,
            metro="",  # filled by run() from the metro key
            state=state,
            details=(f"OSM business listing: {name}. "
                     f"{'Phone '+phone+'. ' if phone else ''}"
                     f"{'Web '+website+'. ' if website else ''}"
                     f"{'Addr: '+addr+'. ' if addr else ''}"
                     f"Geo: {lat_},{lon_}"),
            source="overpass_osm",
            lead_score=55 + (10 if phone else 0),
            url=website or "",
            raw={"lat": lat_, "lon": lon_, "osm_tags": tags},
        ))
        if len(out) >= limit:
            break
    return out


def run(metro: Optional[str] = None) -> Iterator[LeadCandidate]:
    """Yield Overpass leads for one metro (or all known metros)."""
    targets = {metro: METRO_COORDS[metro]} if metro and metro in METRO_COORDS \
        else METRO_COORDS
    for m, (lat, lon) in targets.items():
        try:
            for lead in _fetch(lat, lon):
                lead.metro = m
                yield lead
        except Exception as e:
            print(f"[overpass] metro {m} failed: {e}")
        time.sleep(1.0)  # be polite to the public endpoint


def register_source(reg):
    reg(SourceInfo(
        name="overpass",
        tier="real",
        requires=[],
        description="OpenStreetMap/Overpass local businesses by geo-radius — "
                    "keyless, free, no personal-contact scraping.",
        run_fn=run,
    ))
