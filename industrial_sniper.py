#!/usr/bin/env python3
"""
Empire OS — Industrial Sniper (warehouse-sniper port).
Ports the warehouse-sniper design (Google Places + OSM + storm zones -> webhook)
into our zero-Chrome engine (empire-leads). Targets high-value industrial assets:
warehouses, distribution centers, logistics properties, cold storage.
Adds NWS storm-zone demand triggers (the Empire-USA-Strike angle):
after a storm, those areas need roofing/restore/logistics -> hot leads.

Output: machine-readable signal rows -> feeds advertising_agent + outreach.

Usage:
  python industrial_sniper.py --metro "Dallas, TX" --limit 10
  python industrial_sniper.py --storm --state TX --limit 10
"""
import sys, json, argparse, time
sys.path.insert(0, "/root/empire-leads")

INDUSTRIAL = ["warehouse", "distribution center", "logistics", "cold storage",
              "fulfillment", "freight", "trucking terminal", "industrial"]
# Storm-triggered contractor verticals (Empire-USA-Strike angle)
STORM_VERTICALS = ["roofing", "hvac", "plumbing", "restoration", "tree service",
                   "solar", "contractor", "general_contractor", "water_damage"]

def _discover_retry(discover, *args, **kw):
    """Overpass throttles (429/504) under burst. Retry w/ exp backoff."""
    for attempt in range(4):
        try:
            return discover(*args, **kw)
        except Exception as e:
            if attempt == 3:
                raise
            wait = 2 ** attempt * 5  # 5,10,20s
            time.sleep(wait)

def snipe(metro="Dallas, TX", limit=10, storm=False, state=None):
    from empire_leads.engine import discover
    rows = []
    if storm:
        # storm-triggered demand: NWS alerts -> areas needing rebuild/logistics
        try:
            s = _discover_retry(discover, "storm", state=state or "TX", sources=["nws"], limit=limit)
            for l in (s.leads if hasattr(s, "leads") else []):
                rows.append({"signal": "storm_alert", "asset": l.name, "area": l.address,
                             "trigger": "severe_weather", "intent": "high",
                             "verticals": STORM_VERTICALS[:4]})
        except Exception:
            pass
    # industrial asset scan via Overpass (skip during rate limit recovery)
    if not storm:
        for v in INDUSTRIAL:
            try:
                r = _discover_retry(discover, v, near=metro, radius=30000,
                                    limit=max(2, limit // 3), sources=["overpass"])
                for l in (r.leads if hasattr(r, "leads") else []):
                    rows.append({"signal": "industrial_asset", "asset": l.name,
                                 "email": l.email or "", "phone": l.phone or "",
                                 "website": l.website or "", "city": l.city or "", "state": l.state or "",
                                 "trigger": v, "intent": "medium",
                                 "verticals": ["warehouse", "logistics", "commercial_roofing"]})
            except Exception:
                pass
    return rows[:limit]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--metro", default="Dallas, TX")
    ap.add_argument("--state", default="TX")
    ap.add_argument("--storm", action="store_true")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--out", default="/root/feedback/industrial_leads.jsonl")
    a = ap.parse_args()
    rows = snipe(a.metro, a.limit, a.storm, a.state)
    with open(a.out, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"[sniper] {len(rows)} industrial signals -> {a.out}")
    for r in rows[:5]:
        print("  ", r["signal"], "|", r.get("asset"), "|", r.get("city", r.get("area", "")))

if __name__ == "__main__":
    main()