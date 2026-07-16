
import json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, "/root/empire_os")
import requests

HUB  = os.environ.get("HUB_URL", "http://10.118.155.218:8081")
FB   = Path("/root/feedback")
LOG  = FB / "b2b_log.jsonl"
INTERVAL = int(os.environ.get("INTERVAL_SEC", str(6 * 3600)))
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

def log(level, msg, **fields):
    e = {"ts": datetime.now(timezone.utc).isoformat(), "level": level, "msg": msg, **fields}
    FB.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(e) + "\n")
    if level in ("ERROR", "EVENT"):
        print(json.dumps(e), flush=True)

def overpass_scan(metro: str, niche: str, limit: int = 10):
    q = f"""[out:json][timeout:20];area[name="{metro}"]->.a;nwr["name"]["{niche}"](area.a);out center {limit};"""
    try:
        r = requests.post(OVERPASS_URL, data={"data": q}, timeout=25)
        if r.status_code != 200: return []
        rows = []
        for el in r.json().get("elements", []):
            t = el.get("tags") or {}
            lat = el.get("lat") or (el.get("center") or {}).get("lat")
            lon = el.get("lon") or (el.get("center") or {}).get("lon")
            rows.append({
                "kind": "b2b",
                "name": t.get("name",""),
                "phone": t.get("phone") or t.get("contact:phone",""),
                "email": t.get("email") or t.get("contact:email",""),
                "address": t.get("addr:full") or t.get("addr:street",""),
                "city": t.get("addr:city",""), "state": t.get("addr:state",""),
                "postcode": t.get("addr:postcode",""),
                "category": t.get("amenity") or t.get("shop") or t.get("office") or niche,
                "website": t.get("website",""),
                "lat": lat, "lon": lon,
                "source": "openstreetmap",
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "raw": {k: t.get(k) for k in ("name","phone","website","addr:city","addr:state")}
            })
        return rows
    except Exception as e:
        log("ERROR", "overpass_fail", metro=metro, niche=niche, err=str(e)[:150])
        return []

def hot_metros():
    try:
        r = requests.get(f"{HUB}/v1/swarm/ledger", timeout=8).json()
        heat = r.get("by_lane", {}) if isinstance(r, dict) else {}
        return sorted(heat.items(), key=lambda kv: -kv[1])[:10]
    except Exception: return []

def post(b):
    try: return requests.post(f"{HUB}/v1/b2b/direct", json=b, timeout=8).json().get("ok", False)
    except: return False

def cycle():
    lanes = hot_metros()
    log("CYCLE_START", "b2b cycle", lanes=len(lanes))
    posted = 0
    for lane_key, _ in lanes:
        try: niche, metro = lane_key.split(":")
        except: continue
        for row in overpass_scan(metro, niche, 10):
            if not (row.get("phone") or row.get("email")): continue
            row["lane_key"] = lane_key
            if post(row): posted += 1
            if posted >= 25: break
        if posted >= 25: break
    log("CYCLE_END", "b2b complete", posted=posted, lanes=len(lanes))

if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] b2b-scraper starting - {INTERVAL}s", flush=True)
    time.sleep(45)
    while True:
        try: cycle()
        except Exception as e: log("ERROR", "cycle", err=str(e)[:200])
        time.sleep(INTERVAL)
