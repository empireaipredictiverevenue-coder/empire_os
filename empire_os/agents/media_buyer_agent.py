"""
Empire OS v3 — media-buying agent
==================================

Plans + reports PPC media spend across channels (native, search,
social). Recommend-only — humans (you) approve and the human side
of marketing-agent triggers the spend.

Outputs:
  - /root/feedback/media_buy_plan.jsonl
  - /root/feedback/marketing_log.jsonl (cross-posted; tracks plan)
"""
from __future__ import annotations
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

import requests

HUB    = os.environ.get("HUB_URL", "http://127.0.0.1:8000")
FB     = Path("/root/feedback")
PLAN   = FB / "media_buy_plan.jsonl"
LOG    = FB / "marketing_log.jsonl"
INTERVAL = int(os.environ.get("INTERVAL_SEC", str(3600)))  # 1h cadence


def log(level, msg, **fields):
    e = {"ts": datetime.now(timezone.utc).isoformat(),
         "level": level, "msg": msg, **fields}
    FB.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps({**e, "src": "media_buyer"}) + "\n")
    with open(PLAN, "a") as f:
        f.write(json.dumps(e) + "\n")


def _hub_get(p, **k):
    try:
        return requests.get(f"{HUB}{p}", params=k, timeout=10).json()
    except Exception:
        return {}


def plan() -> dict:
    """Read cold/contacted audience + lead counts, build a plan."""
    counts = _hub_get("/v1/leads/counts")
    pending = counts.get("by_status", {}).get("pending", 0)
    delivered = counts.get("by_status", {}).get("delivered", 0)
    prospects = _hub_get("/v1/outreach/prospects/pending", limit=200)
    cold = len(prospects.get("prospects", []))

    # Naive budget split
    # - native ads (CodeWise-style ad arbitrage) gets most of budget
    # - social gets 30% if cold audience is large
    # - search gets the rest
    native_pct  = 0.50
    social_pct  = 0.20 if cold > 50 else 0.10
    search_pct  = 1.0 - native_pct - social_pct

    # Daily budget heuristic: $1 per cold prospect + $0.05 per pending lead
    daily_budget_usdc = round(cold * 1.0 + pending * 0.05, 2)

    return {
        "daily_budget_usdc": daily_budget_usdc,
        "splits": {
            "native":  native_pct,
            "social":  social_pct,
            "search":  search_pct,
        },
        "target_cold_prospects": cold,
        "target_pending_leads":  pending,
        "delivered_proof":       delivered,
        "notes": [
            f"Native feeds head 5 (CPC + click-through pipeline)",
            f"Social retargets {cold} cold prospects",
            f"Search catches high-intent ['plumbing','hvac','roofing'] terms",
        ],
    }


if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] media-buyer starting — {INTERVAL}s",
          flush=True)
    while True:
        try:
            p = plan()
            log("PLAN", "media_buy_plan", **p)
            print(json.dumps(p), flush=True)
        except Exception as e:
            log("ERROR", "plan_failed", err=str(e)[:200])
        time.sleep(INTERVAL)
