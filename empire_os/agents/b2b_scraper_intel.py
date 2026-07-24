"""
Empire OS v3 — B2B Lead Scraper (intelligence-wired)
====================================================

Replaces b2b_scraper_agent.py with proper intelligence pipeline:
  1. Pulls hot lanes from /v1/swarm/lane-heat (real DB, not empty jsonl)
  2. Falls back to canonical lane list if heat is empty
  3. Queries Overpass for matching businesses (no API key)
  4. Routes each candidate through intelligence_integration.enrich_lead()
  5. Posts enriched leads to /v1/b2b/direct (now exists)
  6. Persists cycle log

Cadence: 6h.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
sys.path.insert(0, "/root/empire_os/empire_os")
import requests

HUB = os.environ.get("HUB_URL", "http://127.0.0.1:8081")
# Write to in-container path; host bind-mount at /root/feedback is uid 1000000.
FB = Path("/root/empire_os/logs/b2b_intel")
LOG = FB / "cycle.jsonl"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
INTERVAL = int(os.environ.get("INTERVAL_SEC", str(6 * 3600)))

# Fallback lane list when /v1/swarm/lane-heat is empty
DEFAULT_LANES = [
    ("roofing", "DFW"), ("roofing", "HOU"), ("roofing", "PHL"),
    ("hvac", "DFW"), ("hvac", "HOU"), ("hvac", "ATL"),
    ("plumbing", "DFW"), ("plumbing", "CHI"), ("plumbing", "MIA"),
    ("electrical", "LAX"), ("electrical", "BOS"),
    ("water_damage", "DFW"), ("fire_damage", "LAX"),
    ("legal_services", "LAX"), ("dental", "CHI"),
    ("real_estate", "MIA"), ("commercial_roofing", "DEN"),
]

# Overpass tag mapping per niche
NICHE_TAGS = {
    "roofing": "craft=roofer",
    "residential_roofing": "craft=roofer",
    "roof_repair": "craft=roofer",
    "commercial_roofing": "craft=roofer",
    "hvac": "craft=hvac",
    "plumbing": "craft=plumber",
    "electrical": "craft=electrician",
    "water_damage": "craft=water_damage_restoration",
    "fire_damage": "craft=fire_damage_restoration",
    "mold_remediation": "craft=mold_remediation",
    "storm_damage": "craft=water_damage_restoration",
    "legal_services": "office=lawyer",
    "dental": "amenity=dentist",
    "real_estate": "office=estate_agent",
    "insurance": "office=insurance",
    "managed_it": "office=it",
    "marketing": "office=advertising",
}

# Metro name + center coords for Overpass area queries
METROS = {
    "NYC": (40.712776, -74.005974), "LAX": (34.052235, -118.243683),
    "CHI": (41.878113, -87.629799), "DFW": (32.776672, -96.796888),
    "HOU": (29.763284, -95.363271), "ATL": (33.749001, -84.387978),
    "MIA": (25.761680, -80.191790), "BOS": (42.360083, -71.058880),
    "SFO": (37.774929, -122.419418), "DEN": (39.739236, -104.984917),
    "PHL": (39.952583, -75.165222), "PHX": (33.448376, -112.074036),
}

UA = "EmpireOS/3.0 (+https://empire-ai.co.uk)"


def log(level, msg, **fields):
    e = {"ts": datetime.now(timezone.utc).isoformat(),
         "level": level, "msg": msg, **fields}
    FB.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(e) + "\n")
    if level in ("ERROR", "CYCLE_START", "CYCLE_END", "EVENT"):
        print(json.dumps(e), flush=True)


def fetch_hot_lanes(limit: int = 10) -> list[tuple[str, str]]:
    """Read /v1/swarm/lane-heat; return [(niche, metro)] sorted by heat."""
    try:
        r = requests.get(f"{HUB}/v1/swarm/lane-heat", timeout=8)
        if r.status_code != 200: return []
        data = r.json()
        lanes = []
        for key, count in data.get("by_lane", {}).items():
            # Skip non-source/tier keys
            if not key or ":" not in key: continue
            ktype, kval = key.split(":", 1)
            if ktype == "source" and "lane_leads" in kval.lower():
                # source:lane_leads_seed_X — derive metro from suffix
                parts = kval.split("_")
                metro = parts[-1].upper() if parts else ""
                lanes.append(("roofing", metro))
            elif ktype == "tier":
                continue  # tier keys don't carry metro info
        # Filter to ones with valid metros
        return [l for l in lanes if l[1] in METROS][:limit]
    except Exception as e:
        log("ERROR", "lane_heat_fail", err=str(e)[:150])
        return []


def overpass_scan(niche: str, metro: str, limit: int = 15) -> list[dict]:
    """Query Overpass for businesses matching niche+metro."""
    if niche not in NICHE_TAGS or metro not in METROS:
        return []
    lat, lon = METROS[metro]
    tag = NICHE_TAGS[niche]
    radius = 25000  # 25km
    q = (f'[out:json][timeout:20];'
         f'nwr["{tag.split("=")[0]}"="{tag.split("=")[1]}"]'
         f'(around:{radius},{lat},{lon});'
         f'out center {limit};')
    try:
        r = requests.post(OVERPASS_URL,
                          data={"data": q},
                          headers={"User-Agent": UA},
                          timeout=25)
        if r.status_code != 200: return []
        rows = []
        for el in r.json().get("elements", []):
            t = el.get("tags") or {}
            lat_ = el.get("lat") or (el.get("center") or {}).get("lat")
            lon_ = el.get("lon") or (el.get("center") or {}).get("lon")
            name = (t.get("name") or "").strip()
            if not name: continue
            # Extract contact fields
            phone = t.get("phone") or t.get("contact:phone") or ""
            email = t.get("email") or t.get("contact:email") or ""
            website = t.get("website") or t.get("contact:website") or ""
            # Skip rows without any contact info — no point enriching
            if not (phone or email or website):
                continue
            rows.append({
                "name": name,
                "phone": phone,
                "email": email,
                "address": t.get("addr:full") or t.get("addr:street") or "",
                "city": t.get("addr:city") or "",
                "state": t.get("addr:state") or "",
                "postcode": t.get("addr:postcode") or "",
                "category": t.get("amenity") or t.get("shop") or t.get("office") or "",
                "website": website,
                "lat": lat_, "lon": lon_,
                "lane_key": f"{niche}:{metro}",
                "source": "overpass_b2b",
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "raw": {"overpass_id": el.get("id"), "tags": list(t.keys())[:20]},
            })
        return rows
    except Exception as e:
        log("ERROR", "overpass_fail", niche=niche, metro=metro, err=str(e)[:150])
        return []


class _Cand:
    """Plain object for enrich_lead() — needs attribute access."""
    pass


def build_candidate(row: dict, niche: str, metro: str):
    c = _Cand()
    c.name = row["name"]
    c.email = row.get("email", "")
    c.phone = row.get("phone", "")
    c.niche = niche
    c.metro = metro
    c.state = row.get("state", "")[:2].upper()
    c.details = (f"B2B Overpass scan: {niche} in {metro}, "
                 f"phone={'yes' if c.phone else 'no'}")
    c.source = "b2b_intel"
    c.lead_score = 70  # base for direct OSM data
    c.url = row.get("website", "")
    c.raw = row
    return c


def post_to_hub(enriched, row: dict) -> int | None:
    try:
        payload = {
            "kind": "b2b",
            "name": row["name"],
            "phone": row.get("phone", ""),
            "email": row.get("email", ""),
            "address": row.get("address", ""),
            "city": row.get("city", ""),
            "state": row.get("state", ""),
            "postcode": row.get("postcode", ""),
            "category": row.get("category", "") or enriched.omega_tier,
            "website": row.get("website", ""),
            "lat": row.get("lat"),
            "lon": row.get("lon"),
            "lane_key": row.get("lane_key", ""),
            "source": "overpass_b2b",
            "scraped_at": row.get("scraped_at", ""),
            "omega_tier": enriched.omega_tier,
            "cortex_score": enriched.cortex_score,
            "buyer_count": len(enriched.buyer_matches or []),
        }
        r = requests.post(f"{HUB}/v1/b2b/direct",
                          json=payload, timeout=8)
        if r.status_code == 200:
            return r.json().get("record_id")
    except Exception as e:
        log("ERROR", "post_fail", name=row.get("name", "")[:30], err=str(e)[:120])
    return None


def cycle():
    log("CYCLE_START", "b2b-intel cycle start")
    from intelligence_integration import enrich_lead, push_to_a2a
    lanes = fetch_hot_lanes(limit=10)
    if not lanes:
        log("EVENT", "lane_heat_empty_fallback",
            fallback_count=len(DEFAULT_LANES))
        lanes = DEFAULT_LANES[:10]
    log("EVENT", "lanes_loaded", lanes=lanes[:5], total=len(lanes))

    total_scanned = 0
    total_posted = 0
    total_pushed_to_a2a = 0

    for niche, metro in lanes:
        rows = overpass_scan(niche, metro, limit=15)
        total_scanned += len(rows)
        for row in rows:
            # Skip rows without contact info
            if not (row.get("phone") or row.get("email") or row.get("website")):
                continue
            cand = build_candidate(row, niche, metro)
            try:
                enriched = enrich_lead(cand, quick=True)
            except Exception as e:
                log("ERROR", "enrich_fail", name=row["name"][:30],
                    err=str(e)[:120])
                continue
            rec_id = post_to_hub(enriched, row)
            if rec_id:
                total_posted += 1
            # Push to A2A only for hot tiers
            if enriched.omega_tier in ("S", "A"):
                try:
                    if push_to_a2a(enriched):
                        total_pushed_to_a2a += 1
                except Exception:
                    pass
        # Rate limit between metros
        time.sleep(1.5)

    log("CYCLE_END", "b2b-intel cycle done",
        scanned=total_scanned, posted=total_posted,
        pushed_to_a2a=total_pushed_to_a2a)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--daemon", action="store_true")
    args = ap.parse_args()
    FB.mkdir(parents=True, exist_ok=True)
    print(f"[{datetime.now(timezone.utc).isoformat()}] b2b-intel online"
          f" — interval={INTERVAL}s", flush=True)
    if not args.daemon:
        cycle()
        return
    while True:
        try: cycle()
        except Exception as e:
            log("ERROR", "cycle", err=str(e)[:200])
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
