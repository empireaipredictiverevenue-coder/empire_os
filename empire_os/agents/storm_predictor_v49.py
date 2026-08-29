#!/usr/bin/env python3
"""
Empire OS v49 - Storm Predictor (Warp Scout) - Adapted for existing storm_forecasts table
===========================================
Uses existing storm_forecasts table schema: id, updated_at, forecasts (JSON), count
"""
import math, time, logging, os, sys, json
from datetime import datetime, timezone

# Load Empire OS env
sys.path.insert(0, "/root/empire_os")
from dotenv import load_dotenv
load_dotenv("/root/empire_os/.env", override=True)

import requests
from supabase import create_client

log = logging.getLogger("empire.storm")
_sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))

# SPC MapServer layers: day 1, day 2, day 3 categorical outlooks
DAY_LAYERS = {
    1: 1,   # today
    2: 9,   # tomorrow
    3: 17,  # day 3
}

# Risk level mapping (SPC dn values -> human labels)
RISK = {
    2: "THUNDERSTORM",
    3: "MARGINAL",
    4: "SLIGHT",
    5: "ENHANCED",
    6: "MODERATE",
    7: "HIGH",
}

RISK_RANK = {
    2: 2,
    3: 3,
    4: 4,
    5: 5,
    6: 6,
    7: 7,
}

# Monitored metros from Empire OS lane system
METROS = {
    "Wichita":      (37.6872, -97.3301),
    "Dallas":       (32.7767, -96.7970),
    "OKC":          (35.4676, -97.5164),
    "Houston":      (29.7604, -95.3698),
    "Tulsa":        (36.1540, -95.9928),
    "Kansas City":  (39.0997, -94.5786),
    "San Antonio":  (29.4241, -98.4936),
    "Memphis":      (35.1495, -90.0490),
    "St. Louis":    (38.6270, -90.1994),
    "Nashville":    (36.1627, -86.7816),
}

def haversine_miles(lat1, lon1, lat2, lon2):
    """Great-circle distance in miles between two points."""
    R = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def min_dist_to_ring(lat, lon, ring):
    """Minimum distance from point to a polygon ring (list of [lon,lat] coords)."""
    return min(haversine_miles(lat, lon, c[1], c[0]) for c in ring)

def point_in_ring(pt, ring):
    """Ray-casting point-in-polygon for a GeoJSON ring."""
    x, y = pt
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside

def fetch_layer(layer_id):
    """Fetch a single SPC outlook layer from NOAA MapServer."""
    url = (
        f"https://mapservices.weather.noaa.gov/vector/rest/services/outlooks/"
        f"SPC_wx_outlks/MapServer/{layer_id}/query"
    )
    params = {
        "where": "1=1",
        "outFields": "dn,valid,label",
        "returnGeometry": "true",
        "f": "geojson"
    }
    try:
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        return r.json().get("features", [])
    except Exception as e:
        log.error(f"[storm] layer {layer_id} fetch error: {e}")
        return []

def assess():
    """
    Check all monitored metros against NOAA SPC 3-day outlooks.
    Returns list of dicts for metros at SLIGHT (risk_rank>=4) or higher.
    Each dict: {metro, day, risk_level, risk_rank, lat, lon}
    """
    forecasts = []
    for day, layer in DAY_LAYERS.items():
        feats = fetch_layer(layer)
        for metro, (lat, lon) in METROS.items():
            best_risk = 0
            for f in feats:
                props = f.get("properties", {})
                dn = props.get("dn")
                if dn not in RISK:
                    continue
                geom = f.get("geometry", {})
                rings = []
                if geom.get("type") == "Polygon":
                    rings = geom.get("coordinates", [])
                elif geom.get("type") == "MultiPolygon":
                    for poly in geom.get("coordinates", []):
                        rings.extend(poly)
                for ring in rings:
                    inside = point_in_ring((lon, lat), ring)
                    near = (not inside) and min_dist_to_ring(lat, lon, ring) <= 100
                    if inside or near:
                        if RISK_RANK.get(dn, 0) > RISK_RANK.get(best_risk, 0):
                            best_risk = dn
                        break
            if best_risk >= 4:  # SLIGHT or higher
                forecasts.append({
                    "metro": metro,
                    "day": day,
                    "risk_level": RISK[best_risk],
                    "risk_rank": RISK_RANK[best_risk],
                    "lat": lat,
                    "lon": lon,
                })
                log.info(f"[PREDICT] Day {day}: {metro} = {RISK[best_risk]} risk")
    return forecasts

def save_forecasts(forecasts):
    """Upsert forecasts to Supabase storm_forecasts table (existing schema)."""
    if not forecasts:
        return
    try:
        # Get max id for new insert (id is not auto-increment)
        max_id_res = _sb.table("storm_forecasts").select("id").order("id", desc=True).limit(1).execute()
        next_id = (max_id_res.data[0]["id"] + 1) if max_id_res.data else 1
        
        # Insert ONE row with all forecasts (original schema design)
        forecast_json = json.dumps(forecasts)
        row = {
            "id": next_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "forecasts": forecast_json,
            "count": len(forecasts)
        }
        
        _sb.table("storm_forecasts").insert(row).execute()
        
        log.info(f"[storm] saved {len(forecasts)} forecast(s) to Supabase (id={next_id})")
    except Exception as e:
        log.error(f"[storm] save error: {e}")

def heartbeat(count):
    """Ping agent_registry so the overseer knows we are alive."""
    try:
        _sb.table("agent_registry").upsert({
            "agent_name": "storm_predictor_v49",
            "status": "ACTIVE",
            "last_ping": datetime.now(timezone.utc).isoformat(),
            "enabled": True,
        }, on_conflict="agent_name").execute()
    except Exception as e:
        log.warning(f"[storm] heartbeat error: {e}")

def run_once():
    """Single assessment cycle - for cron/systemd timer."""
    try:
        forecasts = assess()
        save_forecasts(forecasts)
        heartbeat(0)
        return len(forecasts)
    except Exception as e:
        log.error(f"[storm] cycle error: {e}")
        return 0

def run():
    """Main loop — runs as a mesh agent, polls every 30 minutes."""
    INTERVAL = 1800  # 30 minutes
    count = 0
    print("[PREDICT] Storm Predictor v49 (Warp Scout) starting...")
    while True:
        try:
            forecasts = assess()
            save_forecasts(forecasts)
            heartbeat(count)
            print(f"[PREDICT] Cycle done. {len(forecasts)} metro-risk forecasts.")
        except Exception as e:
            log.error(f"[storm] cycle error: {e}")
        count += 1
        time.sleep(INTERVAL)

if __name__ == "__main__":
    import argparse
    import json
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="Run single assessment and exit")
    ap.add_argument("--daemon", action="store_true", help="Run continuous loop (30 min interval)")
    args = ap.parse_args()
    
    if args.once:
        n = run_once()
        print(f"[PREDICT] Single run complete. {n} forecasts generated.")
    elif args.daemon:
        run()
    else:
        # Default: single run for testing
        results = assess()
        if results:
            for r in results:
                print(f"  {r['metro']} Day {r['day']}: {r['risk_level']} (rank {r['risk_rank']})")
        else:
            print("No significant storm risk in monitored metros right now.")