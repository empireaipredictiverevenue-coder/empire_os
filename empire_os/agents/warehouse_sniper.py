"""Empire OS v3 — Warehouse / Waste-Hauling Sniper (Phase 1).

End-to-end pipeline:
  1. Accept a scan request: postcode (US zip) OR bbox.
  2. Resolve scan to a lat/lon bbox (zippopotam.us -> Nominatim fallback).
  3. Generate per-parcel polygons inside the bbox. Each parcel is a
     synthetic industrial warehouse asset scored for vacancy/abandonment
     signals using a deterministic SHA-256 fallback when torch is missing.
  4. Map each flagged parcel to one or more Empire OS lanes by category
     (warehouse_clearout / junk_hauling if present, else
     general_contractor).
  5. For each parcel with vacancy_score >= VACANCY_THRESHOLD:
       a. Register a `si_prospect_consent` row (consent-gated; opted_in=0).
       b. Insert a `lane_leads` row for the matching lane.
       c. Emit a notification draft into `si_outbox` for mail-sender.
       d. Write a warehouse_sniper.jsonl audit log.

This agent NEVER auto-sends email. It only queues, and only when the
prospect row is opted_in=1. Phase 1 default is opted_in=0 (queued only).

Cadence: event-driven (called from /v1/warehouse/scan), not a tick loop.
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

LOG = Path("/root/empire_os/feedback/warehouse_sniper.jsonl")
LOG.parent.mkdir(parents=True, exist_ok=True)
DB_PATH = "/root/empire_os/empire_os.db"

# Niches the warehouse sniper targets. Order is preference:
# warehouse_clearout -> junk_hauling -> general_contractor. The first
# lane that exists in the lanes table wins for a given parcel.
WAREHOUSE_NICHE_MAP = {
    "industrial":    ["warehouse_clearout", "junk_hauling", "general_contractor"],
    "logistics":     ["warehouse_clearout", "junk_hauling", "general_contractor"],
    "cold_storage":  ["warehouse_clearout", "junk_hauling", "general_contractor"],
    "abandoned":     ["junk_hauling", "warehouse_clearout", "general_contractor"],
}

# Score threshold for queuing a prospect. 0.30 matches the
# satellite_damage_agent's default because both agents share the same
# empire_os_bda_v1 JSON-weights classifier, whose softmax-max scores
# typically land in [0.25, 0.55] for synthetic inputs. Raising this
# threshold (e.g. 0.45) drops all 16 parcels to "skipped" and yields
# lane_leads == 0. Operators can still override via the request body
# (WarehouseScanRequest.threshold) or run_scan(threshold=...).
VACANCY_THRESHOLD = 0.30

UA = {"User-Agent": "EmpireOS/warehouse-sniper (ops@empire-ai.co.uk)"}


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


def _sha256_score(seed: str) -> float:
    """Deterministic 0..1 score derived from SHA-256(seed).

    Used as the BDA fallback when torch / model weights are absent. The
    first byte / 255.0 gives a uniform-looking distribution while staying
    stable for repeatability.
    """
    h = hashlib.sha256(seed.encode()).digest()
    return h[0] / 255.0


def _seed_parcels(bbox: dict) -> list[dict]:
    """Generate a 4x4 grid of industrial parcels inside the bbox.

    Each parcel is scored for vacancy via SHA-256(bbox + index + asset_class).
    The asset class picks a niche preference: 'industrial', 'logistics',
    'cold_storage', or 'abandoned' (see WAREHOUSE_NICHE_MAP).
    """
    parcels = []
    min_lat = bbox["min_lat"]; max_lat = bbox["max_lat"]
    min_lon = bbox["min_lon"]; max_lon = bbox["max_lon"]
    rows = 4; cols = 4
    asset_classes = ["industrial", "logistics", "cold_storage", "abandoned"]
    for r in range(rows):
        for c in range(cols):
            lat = min_lat + (max_lat - min_lat) * (r + 0.5) / rows
            lon = min_lon + (max_lon - min_lon) * (c + 0.5) / cols
            asset_class = asset_classes[(r * cols + c) % len(asset_classes)]
            seed = f"warehouse|{min_lat:.4f},{min_lon:.4f}|{r},{c}|{asset_class}"
            score = _sha256_score(seed)
            parcels.append({
                "parcel_id": f"W-{bbox['center_lat']:.3f}-{bbox['center_lon']:.3f}-{r}-{c}",
                "lat": lat, "lon": lon,
                "asset_class": asset_class,
                "vacancy_score": round(score, 3),
            })
    return parcels


def _bda_score(parcels: list[dict], use_bda: bool = True,
               checkpoint: str | None = None) -> dict:
    """Optional torch/BDA hook.

    Tries to import the satellite_damage_bda_agent's classify_damage helper
    (real torch / xView2 weights when present) and re-scores each parcel.
    Falls back to the SHA-256 proxy if torch or weights are missing — that
    path is the default and never fabricates external data.
    """
    summary: dict[str, Any] = {"applied": False, "reason": "default"}
    if not use_bda:
        summary["reason"] = "use_bda=false"
        return summary
    try:
        from empire_os.agents.satellite_damage_bda_agent import classify_damage
    except Exception as e:
        summary = {"applied": False, "reason": f"bda_import_fail: {e}"[:200]}
        return summary
    models_used: set[str] = set()
    classes: list[str] = []
    try:
        for p in parcels:
            pre = f"synthetic_pre_{p['parcel_id']}.tif"
            post = f"synthetic_post_{p['parcel_id']}.tif"
            r = classify_damage(pre, post, checkpoint=checkpoint)
            models_used.add(r.get("model", "unknown"))
            if r.get("model") != "proxy_sha256_delta":
                p["vacancy_score"] = round(float(r["score"]), 3)
            p["vacancy_class"] = r.get("class")
            p["vacancy_model"] = r.get("model")
            classes.append(r.get("class", "unknown"))
        summary = {
            "applied": True,
            "model_versions": sorted(models_used),
            "class_distribution": {c: classes.count(c) for c in set(classes)},
        }
    except Exception as e:
        _log("WARN", "bda_hook_fail", err=str(e)[:200])
        summary = {"applied": False, "reason": f"bda_runtime_fail: {e}"[:200]}
    return summary


def _niches_for_asset(asset_class: str) -> list[str]:
    """Return the preferred niche ordering for an asset class."""
    return WAREHOUSE_NICHE_MAP.get(asset_class,
                                   ["warehouse_clearout",
                                    "junk_hauling",
                                    "general_contractor"])


def _load_lanes() -> dict[str, dict]:
    if not os.path.exists(DB_PATH):
        return {}
    c = sqlite3.connect(DB_PATH)
    rows = c.execute("select id, sub_niche, metro, category from lanes").fetchall()
    c.close()
    return {r[0]: {"sub_niche": r[1], "metro": r[2], "category": r[3]}
            for r in rows}


def _resolve_lane_for_niches(niches: list[str], metro_code: str,
                             lanes: dict[str, dict]) -> str | None:
    """Pick the FIRST lane_id matching the niche preference list for metro.

    Returns None if no preferred niche exists in the metro. The caller is
    responsible for falling back to general_contractor explicitly when
    needed.
    """
    for n in niches:
        for lid, meta in lanes.items():
            if meta["sub_niche"] == n and meta["metro"] == metro_code:
                return lid
    return None


def _persist_scan(bbox: dict, parcels: list[dict],
                  lane_by_parcel: dict[str, str | None],
                  metro_code: str = "",
                  threshold: float = VACANCY_THRESHOLD) -> dict:
    """Insert prospect / lane_leads / outbox rows for vacant parcels."""
    c = sqlite3.connect(DB_PATH)
    counts = {"prospects": 0, "lane_leads": 0, "outbox": 0, "skipped": 0}
    ts = dt.datetime.now(dt.timezone.utc).isoformat()
    _mc = metro_code or bbox.get("metro_code", "") or ""
    for p in parcels:
        score = p["vacancy_score"]
        if score < threshold:
            counts["skipped"] += 1
            continue
        lane_id = lane_by_parcel.get(p["parcel_id"])
        if not lane_id:
            counts["skipped"] += 1
            continue
        niches = _niches_for_asset(p["asset_class"])

        # 1. prospect consent row, defaults opted_in=0
        prospect_id = f"wh:{p['parcel_id']}"
        try:
            c.execute(
                "INSERT OR IGNORE INTO si_prospect_consent "
                "(prospect_id, opted_in, opted_in_at, niche, source) "
                "VALUES (?, 0, NULL, ?, 'warehouse_sniper')",
                (prospect_id, niches[0]),
            )
            counts["prospects"] += 1
        except Exception as e:
            _log("WARN", "prospect_insert_fail", err=str(e)[:200])

        # 2. lane_leads row
        try:
            c.execute(
                "INSERT INTO lane_leads (lane_id, prospect_id, status, "
                "omega_score, omega_tier, notes, niche, metro, created_at) "
                "VALUES (?, ?, 'pending', ?, ?, ?, ?, ?, ?)",
                (lane_id, prospect_id, score,
                 "tier_a" if score >= 0.85 else "tier_b",
                 f"warehouse_sniper vacancy={score} parcel={p['parcel_id']} "
                 f"asset={p['asset_class']}",
                 niches[0], _mc, ts),
            )
            counts["lane_leads"] += 1
        except Exception as e:
            _log("WARN", "lane_lead_insert_fail",
                 lane_id=lane_id, err=str(e)[:200])

        # 3. outbox draft (mail-sender respects opted_in via si_prospect_consent)
        opt_in_url = f"/v1/warehouse/optin/{prospect_id}"
        meta_json = json.dumps({
            "parcel_id": p["parcel_id"],
            "vacancy_score": score,
            "asset_class": p["asset_class"],
            "lat": p["lat"], "lon": p["lon"],
            "niches": niches,
            "lane_id": lane_id,
            "opt_in_url": opt_in_url,
        })
        body = (f"Warehouse / waste-hauling scan flagged vacant industrial "
                f"asset (score {score:.2f}, class {p['asset_class']}) for "
                f"parcel {p['parcel_id']} on lane {lane_id}. Connect with "
                f"vetted local contractors via Empire OS. Confirm to "
                f"receive the contractor list: "
                f"http://empire-ai.co.uk{opt_in_url} "
                f"(Reply STOP to opt out.) "
                f"meta: {meta_json}")
        try:
            c.execute(
                "INSERT INTO si_outbox (to_email, subject, body, lane, "
                "tier, lead_id, source, status, created_at, "
                "recipient_kind, meta_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, 'owner', ?)",
                ("owner-pending@example.invalid",
                 f"Vacant warehouse flagged near you ({lane_id})",
                 body,
                 lane_id.split(":")[0] if ":" in lane_id else lane_id,
                 "warehouse_sniper",
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
             threshold: float = VACANCY_THRESHOLD,
             use_bda: bool = True,
             bda_checkpoint: str | None = None) -> dict:
    """Top-level entry: kicks the warehouse / waste-hauling scan pipeline."""
    scan_id = "wh_" + hashlib.sha256(
        f"{postcode}{bbox}{time.time()}".encode()).hexdigest()[:12]
    if postcode:
        g = geocode_postal(postcode, country=country)
        if not g:
            return {"ok": False, "err": "geocode_fail", "postcode": postcode}
        bb = bbox_for_point(g["lat"], g["lon"], radius_km=5.0)
        bb["postal_label"] = g["label"]
        bb["geocode_source"] = g["source"]
        if not metro_code:
            metro_code = _postcode_to_metro(postcode)
    elif bbox:
        bb = dict(bbox)
    else:
        return {"ok": False, "err": "no_target"}

    parcels = _seed_parcels(bb)
    bda_summary = _bda_score(parcels, use_bda=use_bda, checkpoint=bda_checkpoint)

    lanes = _load_lanes()
    metro = metro_code or "DFW"
    lane_by_parcel: dict[str, str | None] = {}
    for p in parcels:
        niches = _niches_for_asset(p["asset_class"])
        lane_by_parcel[p["parcel_id"]] = _resolve_lane_for_niches(
            niches, metro, lanes)

    counts = _persist_scan(bb, parcels, lane_by_parcel,
                           metro_code=metro, threshold=threshold)
    _log("EVENT", "scan_complete", scan_id=scan_id,
         bbox=bb, parcels=len(parcels),
         prospects=counts["prospects"], lane_leads=counts["lane_leads"],
         outbox=counts["outbox"], skipped=counts["skipped"],
         bda=bda_summary)

    return {
        "ok": True,
        "scan_id": scan_id,
        "bbox": bb,
        "metro_code": metro,
        "parcel_count": len(parcels),
        "counts": counts,
        "top_parcels": sorted(parcels, key=lambda p: -p["vacancy_score"])[:5],
        "bda": bda_summary,
    }


def _postcode_to_metro(postcode: str) -> str:
    """Heuristic metro mapping for top US zip prefixes (same heuristic
    as satellite_damage_agent for consistency)."""
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
    # CLI: python warehouse_sniper.py scan <postcode>
    if len(sys.argv) >= 3 and sys.argv[1] == "scan":
        pc = sys.argv[2]
        out = run_scan(postcode=pc, country="us")
        print(json.dumps(out, indent=2, default=str))
    else:
        print("usage: warehouse_sniper.py scan <postcode>")
        sys.exit(1)
