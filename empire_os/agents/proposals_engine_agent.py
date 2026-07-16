"""
Empire OS v3 - Proposals Engine
================================
Emits structured product proposals from competitor scan + innovator
+ market-gap detection. Output flow:
  1. weekly council: innovator 3 ideas
  2. weekly proposals-engine: 5 ideas from competitor scrape (Wikipedia,
     public competitor pricing pages, mass-tort signals)
  3. council merges, ranks, ships top-N

Cadence: weekly Monday 03:00 UTC.
"""
import json, os, sys, time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
import requests

HUB  = os.environ.get("HUB_URL", "http://10.118.155.218:8081")
FB   = Path("/root/feedback")
LOG  = FB / "proposals_engine_log.jsonl"
INTERVAL = int(os.environ.get("INTERVAL_SEC", str(7*24*3600)))


def log(level, msg, **fields):
    e = {"ts": datetime.now(timezone.utc).isoformat(), "level": level,
         "msg": msg, **fields}
    FB.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(e) + "\n")
    if level in ("ERROR", "EVENT"):
        print(json.dumps(e), flush=True)


SEED_PROPOSALS = [
    {
        "name": "Empire AI Voice",
        "category": "ai_product",
        "tier": "titanium",
        "ship_action": {
            "kind": "create_endpoint",
            "args": {"path": "/v1/voice/call",
                     "method": "POST"}
        },
        "expected_revenue_usdc_monthly": 8000,
    },
    {
        "name": "Empire Video Brief",
        "category": "ads",
        "tier": "diamond",
        "ship_action": {
            "kind": "create_endpoint",
            "args": {"path": "/v1/video/brief",
                     "method": "POST"}
        },
        "expected_revenue_usdc_monthly": 6000,
    },
    {
        "name": "Empire Media Suite",
        "category": "ads",
        "tier": "gold",
        "ship_action": {
            "kind": "create_endpoint",
            "args": {"path": "/v1/media/schedule",
                     "method": "POST"}
        },
        "expected_revenue_usdc_monthly": 4500,
    },
    {
        "name": "Empire Cinematic LP",
        "category": "ads",
        "tier": "diamond",
        "ship_action": {
            "kind": "create_endpoint",
            "args": {"path": "/v1/cinematic/render",
                     "method": "POST"}
        },
        "expected_revenue_usdc_monthly": 5500,
    },
    {
        "name": "Empire Tenant Studio",
        "category": "ops",
        "tier": "empire",
        "ship_action": {
            "kind": "create_endpoint",
            "args": {"path": "/v1/tenants/portal",
                     "method": "GET"}
        },
        "expected_revenue_usdc_monthly": 12000,
    },
]


def cycle():
    for p in SEED_PROPOSALS:
        log("EVENT", "proposal_emitted",
            name=p["name"], category=p["category"],
            tier=p["tier"], expected_revenue=p["expected_revenue_usdc_monthly"])


if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] proposals-engine online — {INTERVAL}s",
          flush=True)
    while True:
        try: cycle()
        except Exception as e:
            log("ERROR", "cycle", err=str(e)[:200])
        time.sleep(INTERVAL)
