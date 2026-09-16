"""Empire OS v3 — Satellite Damage Agent.

Accepts a postcode or bounding box and resolves the target geography.

NO-SIM policy:
  - no synthetic parcels;
  - no synthetic NDVI or damage scores;
  - no proxy/hash-derived damage inference;
  - no prospect, lane lead, or outreach record is created without real
    imagery and real parcel evidence.

Real satellite imagery and parcel ingestion are not yet wired, so scans
currently fail closed with `real_imagery_not_configured`.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, "/root/empire_os")

LOG = Path(
    os.getenv(
        "SATELLITE_DAMAGE_LOG",
        "/srv/empire_os/runtime/feedback/satellite_damage.jsonl",
    )
)
LOG.parent.mkdir(parents=True, exist_ok=True)
DB_PATH = "/root/empire_os/empire_os.db"
BDA_WEIGHTS_PATH = "/opt/bda_ckpt/unet_xview2.weights.json"

DAMAGE_NICHE_MAP = {
    "residential": ["residential_roofing", "roof_repair", "storm_damage"],
    "commercial":  ["commercial_roofing", "general_contractor"],
    "industrial":  ["general_contractor", "water_damage"],
}

UA = {"User-Agent": "EmpireOS/satellite-damage (ops@empire-ai.co.uk)"}


def _log(level: str, msg: str, **kw: Any) -> None:
    rec = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(),
           "level": level, "msg": msg, **kw}
    with LOG.open("a") as f:
        f.write(json.dumps(rec) + "\n")


def _http(url: str, timeout: int = 10) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def geocode_postal(postcode: str, country: str = "us") -> dict | None:
    """Return {lat, lon, label} for a postal code."""
    try:
        url = f"https://api.zippopotam.us/{country}/{postcode}"
        with urllib.request.urlopen(url, timeout=8) as r:
            data = json.loads(r.read())
        place = data["places"][0]
        return {
            "lat": float(place["latitude"]),
            "lon": float(place["longitude"]),
            "label": f"{place['place name']}, {place['state abbreviation']}",
            "source": "zippopotam",
        }
    except Exception:
        # Nominatim fallback
        try:
            url = ("https://nominatim.openstreetmap.org/search?postalcode="
                   f"{urllib.parse.quote(postcode)}&countrycodes={country}"
                   "&format=json&limit=1")
            with urllib.request.urlopen(url, timeout=8) as r:
                arr = json.loads(r.read())
            if not arr:
                return None
            return {
                "lat": float(arr[0]["lat"]),
                "lon": float(arr[0]["lon"]),
                "label": arr[0]["display_name"],
                "source": "nominatim",
            }
        except Exception as e:
            _log("WARN", "geocode_fail", postcode=postcode, err=str(e)[:200])
            return None


def bbox_for_point(lat: float, lon: float, radius_km: float = 5.0) -> dict:
    """Approximate bbox around a point."""
    d = radius_km / 111.0  # ~1 deg lat = 111 km
    return {
        "min_lat": lat - d,
        "max_lat": lat + d,
        "min_lon": lon - d,
        "max_lon": lon + d,
        "center_lat": lat,
        "center_lon": lon,
        "radius_km": radius_km,
    }


def bbox_from_cap_event(event_id: str) -> dict | None:
    """Pull a CAP event from satellite_strike_state.json and return bbox."""
    state = Path("/root/feedback/satellite_strike_state.json")
    if not state.exists():
        return None
    j = json.loads(state.read_text())
    for sid in j.get("seen_ids", []):
        if event_id in sid:
            # We don't store polygon coords in state.json (Phase 1 limitation);
            # return a stub and rely on the caller providing a bbox instead.
            return None
    return None


def run_scan(*, postcode: str | None = None,
             bbox: dict | None = None,
             country: str = "us",
             metro_code: str | None = None,
             use_bda: bool = False,
             bda_checkpoint: str | None = None) -> dict:
    """Top-level entry: kicks the scan pipeline."""
    scan_id = "scn_" + hashlib.sha256(
        f"{postcode}{bbox}{time.time()}".encode()).hexdigest()[:12]
    if postcode:
        g = geocode_postal(postcode, country=country)
        if not g:
            return {"ok": False, "err": "geocode_fail", "postcode": postcode}
        bb = bbox_for_point(g["lat"], g["lon"], radius_km=5.0)
        bb["postal_label"] = g["label"]
        bb["geocode_source"] = g["source"]
        if not metro_code:
            # heuristic: DFW for 75*, HOU for 77*, etc.
            metro_code = _postcode_to_metro(postcode)
    elif bbox:
        bb = dict(bbox)
    else:
        return {"ok": False, "err": "no_target"}

    _log("WARN", "scan_blocked_no_real_imagery", scan_id=scan_id, bbox=bb, metro_code=metro_code)
    return {
        "ok": False,
        "err": "real_imagery_not_configured",
        "reason": "Synthetic satellite damage generation is disabled. Real pre/post imagery and parcel data are required.",
        "scan_id": scan_id,
        "bbox": bb,
        "metro_code": metro_code,
        "parcel_count": 0,
        "counts": {"prospects": 0, "lane_leads": 0, "outbox": 0, "skipped": 0},
        "top_parcels": [],
        "bda": {"applied": False, "reason": "real_imagery_not_configured"},
    }


def _postcode_to_metro(postcode: str) -> str:
    """Heuristic metro mapping for top US zip prefixes."""
    p = postcode.strip()
    if p.startswith(("750", "751", "752", "753")):
        return "DFW"
    if p.startswith(("770", "771", "772", "773", "774", "775")):
        return "HOU"
    if p.startswith(("100", "101", "102", "103", "104", "110", "111", "112")):
        return "NYC"
    if p.startswith(("900", "901", "902", "903", "904")):
        return "LAX"
    if p.startswith(("606", "607", "608")):
        return "CHI"
    if p.startswith(("300", "301", "302", "303", "311", "399")):
        return "ATL"
    if p.startswith(("331", "332", "330")):
        return "MIA"
    if p.startswith(("021", "022", "024")):
        return "BOS"
    if p.startswith(("191", "190", "189")):
        return "PHL"
    if p.startswith(("200", "201", "202", "203", "204", "205")):
        return "WDC"
    if p.startswith(("940", "941", "943", "944")):
        return "SFO"
    return "DFW"


if __name__ == "__main__":
    # CLI: python satellite_damage_agent.py scan <postcode>
    if len(sys.argv) >= 3 and sys.argv[1] == "scan":
        pc = sys.argv[2]
        out = run_scan(postcode=pc, country="us")
        print(json.dumps(out, indent=2, default=str))
    else:
        print("usage: satellite_damage_agent.py scan <postcode>")
        sys.exit(1)
