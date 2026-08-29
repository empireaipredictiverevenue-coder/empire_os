"""
Empire OS v3 — contractor scraper agent (browser-enabled).

1. State SOS business/license search (browser-rendered, no key)
   - Texas SOS / TDI
   - Florida DBPR
   - California CSLB
2. Carrier DRP rosters (browser-rendered via empire_os.carrier_rosters)

Posts to /v1/contractors/direct on hub (port 8081).
"""
import json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
import requests

HUB  = os.environ.get("HUB_URL", "http://127.0.0.1:8081")
FB   = Path("/root/feedback")
LOG  = FB / "contractor_log.jsonl"
INTERVAL = int(os.environ.get("INTERVAL_SEC", str(24 * 3600)))

# State contractor discovery — custom per-portal flows (see state_contractor_portals)
STATE_FLOWS = {
    "fl_dbpr": ("FL", "https://www.myfloridalicense.com/wl11.asp"),
    "ca_cslb": ("CA", "https://www.cslb.ca.gov/onlineservices/checklicense.aspx"),
    "tx_sos":  ("TX", "https://mycpa.cpa.state.tx.us/fo/Search/SearchEntities.aspx"),
}

def log(level, msg, **fields):
    e = {"ts": datetime.now(timezone.utc).isoformat(), "level": level, "msg": msg, **fields}
    FB.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(e) + "\n")
    if level in ("ERROR", "EVENT"):
        print(json.dumps(e), flush=True)

def state_search(src_name: str, url: str, niche: str = "contractor") -> list:
    """Dispatch to custom per-portal flow; fall back to Bing-state."""
    st = {"fl_dbpr": "FL", "ca_cslb": "CA", "tx_sos": "TX"}.get(src_name, "")
    try:
        from empire_os import state_contractor_portals as p
        if src_name == "fl_dbpr":
            rows = p.fl_dbpr(niche, "")
        else:
            # CA CSLB is license-number based; TX SOS namefile is not discovery.
            # Use Bing-rendered state discovery for real rows.
            rows = p.bing_state(niche, st)
        log("INFO", "state_search", source=src_name, rows=len(rows))
        return rows
    except Exception as e:
        log("ERROR", "state_search_fail", source=src_name, err=str(e)[:150])
        return []

# Top-tier endpoint: only HOT/WARM pre-qualified leads go here
TOP_TIER = f"{HUB}/v1/contractors/top-tier"
STATE_NICHE = os.environ.get("NICHE", "roofing")
STATE_GEO = os.environ.get("GEO", "FL")

def post_contractor(row):
    try:
        return requests.post(f"{HUB}/v1/contractors/direct", json=row, timeout=8).json().get("ok", False)
    except Exception:
        return False

def post_top_tier(row):
    """Only pre-qualified HOT/WARM leads reach top-tier buyers.
    hub contractor_top_tier_intake expects a single dict."""
    try:
        return requests.post(TOP_TIER, json=row, timeout=8).json().get("ok", False)
    except Exception:
        return False

def cycle_state_db():
    log("STATE_DB_CYCLE_START", "state contractor cycle")
    posted = 0
    from empire_os.lead_qualifier import Qualifier
    q = Qualifier(target_niche=STATE_NICHE, target_geo=STATE_GEO)
    for src_name, (st, url) in STATE_FLOWS.items():
        rows = state_search(src_name, url)
        out = q.qualify(rows)
        # only HOT/WARM to top tier (single dict per call)
        for lead in out["hot"] + out["warm"]:
            lead["source"] = src_name
            if post_top_tier(lead):
                posted += 1
        log("STATE_DB_QUALIFIED", src_name, **out["metrics"])
    log("STATE_DB_CYCLE_END", "state DB contractor cycle complete", posted=posted)
    return posted

def cycle_carrier_rosters():
    log("CARRIER_CYCLE_START", "carrier roster cycle")
    try:
        from empire_os.carrier_rosters import run_all, _ensure_tables
        _ensure_tables()
        result = run_all(store=True)
        # result: {slug: {"ok": bool, "count": int}}
        total = sum(v.get("count", 0) for v in result.values() if isinstance(v, dict))
        carriers = len(result)
        log("CARRIER_CYCLE_END", "carrier roster cycle complete",
            carriers=carriers, new_rows=total)
        return total
    except ImportError:
        log("WARN", "carrier_rosters module not available — skipping")
        return 0
    except Exception as e:
        log("ERROR", "carrier_cycle_fail", err=str(e)[:200])
        return 0

def cycle():
    log("CYCLE_START", "contractor cycle")
    state_posted = cycle_state_db()
    carrier_new = cycle_carrier_rosters()
    log("CYCLE_END", "contractor cycle complete",
        state_db_posted=state_posted, carrier_roster_new=carrier_new)

if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] contractor-scraper starting - {INTERVAL}s", flush=True)
    try:
        from empire_os.carrier_rosters import _ensure_tables
        _ensure_tables()
        log("INFO", "carrier_rosters_schema_ensured")
    except Exception as e:
        log("WARN", "carrier_rosters_schema_init", err=str(e)[:100])
    time.sleep(60)
    while True:
        try: cycle()
        except Exception as e: log("ERROR", "cycle", err=str(e)[:200])
        time.sleep(INTERVAL)
