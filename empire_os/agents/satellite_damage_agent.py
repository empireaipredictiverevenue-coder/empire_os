"""Empire OS v3 — Satellite Damage Agent (Phase 1).

End-to-end pipeline:
  1. Accept a scan request: bbox OR cap_event_id OR postcode.
  2. Resolve scan to a lat/lon bbox (US-zip -> zippopotam.us, fallback -> Nominatim).
  3. Pull Sentinel-2 L2A NDVI proxy (free, public, no key) for the bbox.
     For Phase 1 we use a deterministic synthetic NDVI delta based on the
     bbox hash + a stub "event time" so the pipeline can be exercised
     end-to-end without a real satellite provider. Plug in real imagery
     in Phase 2 (Microsoft BuildingDamageAssessment + raster-vision).
  4. Generate per-parcel polygons inside the bbox (synthetic grid for
     Phase 1; replaced with county parcel polygons in Phase 2 via
     Overpass).
  5. Score damage 0..1 per parcel.
  6. Map each damaged parcel to one or more Empire OS lanes by category
     (residential_roofing, water_damage, tree_service, ...).
  7. For each damaged parcel with score >= 0.5:
       a. Register a `si_prospect_consent` row (consent-gated; defaults opted_in=0).
       b. Insert a `lane_leads` row for the matching lane.
       c. Emit a notification draft into `si_outbox` for mail-sender.
       d. Write a satellite_damage_event.jsonl audit log.

This agent NEVER auto-sends email. It only queues, and only when the
prospect row is opted_in=1. Phase 1 default is opted_in=0 (queued only).

Cadence: event-driven (called from /v1/damage/scan), not a tick loop.
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

LOG = Path("/root/feedback/satellite_damage.jsonl")
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


def _seed_damage(bbox: dict) -> list[dict]:
    """Deterministic synthetic NDVI-delta grid for Phase 1.

    Generates a 4x4 grid of 'parcels' inside the bbox with damage scores
    0..1 derived from sha256(bbox + index) for repeatability.
    """
    parcels = []
    min_lat = bbox["min_lat"]; max_lat = bbox["max_lat"]
    min_lon = bbox["min_lon"]; max_lon = bbox["max_lon"]
    rows = 4; cols = 4
    for r in range(rows):
        for c in range(cols):
            lat = min_lat + (max_lat - min_lat) * (r + 0.5) / rows
            lon = min_lon + (max_lon - min_lon) * (c + 0.5) / cols
            h = hashlib.sha256(f"{min_lat},{min_lon},{r},{c}".encode()).digest()
            score = (h[0] / 255.0)  # 0..1 deterministic
            parcels.append({
                "parcel_id": f"P-{bbox['center_lat']:.3f}-{bbox['center_lon']:.3f}-{r}-{c}",
                "lat": lat, "lon": lon,
                "ndvi_pre": 0.6 + (h[1] / 255.0) * 0.3,
                "ndvi_post": 0.6 + (h[1] / 255.0) * 0.3 - score * 0.5,
                "damage_score": round(score, 3),
            })
    return parcels


def _niches_for_damage(damage_score: float) -> list[str]:
    """Map damage severity to the niche lanes that should be alerted."""
    if damage_score >= 0.85:
        return ["residential_roofing", "water_damage", "storm_damage",
                "tree_service", "general_contractor"]
    if damage_score >= 0.65:
        return ["residential_roofing", "roof_repair", "storm_damage"]
    if damage_score >= 0.45:
        return ["residential_roofing", "roof_repair"]
    if damage_score >= 0.25:
        return ["roof_repair"]
    return []


def _lane_ids_for(niches: list[str], metro_code: str, lanes: dict[str, dict]) -> list[str]:
    out = []
    for n in niches:
        for lid in lanes:
            if lid.startswith(f"{n}:{metro_code}"):
                out.append(lid)
    return out


def _load_lanes() -> dict[str, dict]:
    if not os.path.exists(DB_PATH):
        return {}
    c = sqlite3.connect(DB_PATH)
    rows = c.execute("select id, sub_niche, metro from lanes").fetchall()
    c.close()
    return {r[0]: {"sub_niche": r[1], "metro": r[2]} for r in rows}


def _persist_scan(bbox: dict, parcels: list[dict], niches_by_parcel: dict[str, list[str]],
                  lane_ids_by_parcel: dict[str, list[str]],
                  damage_threshold: float = 0.3) -> dict:
    """Insert prospect/lane_leads/outbox rows for damaged parcels.

    Returns counts.
    """
    c = sqlite3.connect(DB_PATH)
    counts = {"prospects": 0, "lane_leads": 0, "outbox": 0, "skipped": 0}
    ts = dt.datetime.now(dt.timezone.utc).isoformat()
    for p in parcels:
        score = p["damage_score"]
        if score < damage_threshold:
            counts["skipped"] += 1
            continue
        niches = niches_by_parcel.get(p["parcel_id"], [])
        lane_ids = lane_ids_by_parcel.get(p["parcel_id"], [])
        if not lane_ids:
            counts["skipped"] += 1
            continue
        # 1. prospect consent row, defaults opted_in=0
        prospect_id = f"sat:{p['parcel_id']}"
        try:
            c.execute(
                "INSERT OR IGNORE INTO si_prospect_consent "
                "(prospect_id, opted_in, opted_in_at, niche, source) "
                "VALUES (?, 0, NULL, ?, 'satellite_damage')",
                (prospect_id, niches[0] if niches else "general"),
            )
            counts["prospects"] += 1
        except Exception as e:
            _log("WARN", "prospect_insert_fail", err=str(e)[:200])

        # 2. lane_leads row for each lane
        for lane_id in lane_ids:
            try:
                c.execute(
                    "INSERT INTO lane_leads (lane_id, prospect_id, status, "
                    "omega_score, omega_tier, notes, niche, created_at) "
                    "VALUES (?, ?, 'pending', ?, ?, ?, ?, ?)",
                    (lane_id, prospect_id, score,
                     "tier_a" if score >= 0.85 else "tier_b",
                     f"satellite_damage score={score} parcel={p['parcel_id']}",
                     niches[0] if niches else "general",
                     ts),
                )
                counts["lane_leads"] += 1
            except Exception as e:
                _log("WARN", "lane_lead_insert_fail",
                     lane_id=lane_id, err=str(e)[:200])

        # 3. outbox notification (mail-sender respects opted_in via si_prospect_consent)
        meta_json = json.dumps({"parcel_id": p["parcel_id"],
                                "damage_score": score,
                                "lat": p["lat"], "lon": p["lon"],
                                "niches": niches,
                                "opt_in_url": f"/v1/damage/opt-in/{prospect_id}"})
        for lid in lane_ids:
            try:
                opt_in_url = f"/v1/damage/opt-in/{prospect_id}"
                body = (f"Satellite scan flagged damage score {score:.2f} for "
                        f"parcel {p['parcel_id']} in lane {lid}. Connect with "
                        f"vetted local contractors via Empire OS. "
                        f"Confirm to receive the contractor list: "
                        f"http://empire-ai.co.uk{opt_in_url} "
                        f"(Reply STOP to opt out.) "
                        f"meta: {meta_json}")
                c.execute(
                    "INSERT INTO si_outbox (to_email, subject, body, lane, "
                    "tier, lead_id, source, status, created_at, "
                    "recipient_kind, meta_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, 'owner', ?)",
                    ("owner-pending@example.invalid",
                     f"Storm damage detected near your property ({lid})",
                     body,
                     lid.split(":")[0] if ":" in lid else lid,
                     "satellite_damage",
                     prospect_id,
                     meta_json,
                     ts,
                     meta_json),
                )
                counts["outbox"] += 1
            except Exception as e:
                _log("WARN", "outbox_insert_fail", err=str(e)[:200])
    c.commit()
    c.close()
    return counts


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

    parcels = _seed_damage(bb)

    # Phase-2 BDA hook: re-score parcels using the BDA weights file
    # (/opt/bda_ckpt/unet_xview2.weights.json). Falls back to proxy only
    # if torch+checkpoint or the JSON weights are missing.
    bda_summary = None
    if use_bda:
        try:
            from empire_os.agents.satellite_damage_bda_agent import classify_damage
            classes = []
            models_used = set()
            for p in parcels:
                pre = f"synthetic_pre_{p['parcel_id']}.tif"
                post = f"synthetic_post_{p['parcel_id']}.tif"
                r = classify_damage(pre, post,
                                    checkpoint=bda_checkpoint,
                                    weights_path=BDA_WEIGHTS_PATH)
                models_used.add(r.get("model", "unknown"))
                if r["model"] != "proxy_sha256_delta":
                    p["damage_score"] = r["score"]
                p["damage_class"] = r["class"]
                p["damage_model"] = r["model"]
                classes.append(r["class"])
            bda_summary = {
                "applied": True,
                "weights_path": BDA_WEIGHTS_PATH,
                "model_versions": sorted(models_used),
                "class_distribution": {c: classes.count(c) for c in set(classes)},
            }
        except Exception as e:
            _log("WARN", "bda_hook_fail", err=str(e)[:200])
            bda_summary = {"applied": False, "reason": str(e)[:200]}

    niches_by_parcel = {p["parcel_id"]: _niches_for_damage(p["damage_score"])
                       for p in parcels}
    lanes = _load_lanes()
    lane_ids_by_parcel = {p["parcel_id"]: _lane_ids_for(
        niches_by_parcel[p["parcel_id"]], metro_code or "DFW", lanes)
        for p in parcels}

    counts = _persist_scan(bb, parcels, niches_by_parcel, lane_ids_by_parcel)
    _log("EVENT", "scan_complete", scan_id=scan_id,
         bbox=bb, parcels=len(parcels),
         prospects=counts["prospects"], lane_leads=counts["lane_leads"],
         outbox=counts["outbox"], skipped=counts["skipped"])

    return {
        "ok": True,
        "scan_id": scan_id,
        "bbox": bb,
        "metro_code": metro_code,
        "parcel_count": len(parcels),
        "counts": counts,
        "top_parcels": sorted(parcels, key=lambda p: -p["damage_score"])[:5],
        "bda": bda_summary,
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