"""
Empire OS v3 — data-acquisition agent
======================================

Aggressive lead scraper for hot lanes (subscribed niches × metros).
Runs all REAL lead sources against the most-subscribed metro per
niche and posts each candidate to /v1/leads/direct.

Cadence: 6h.
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
from empire_os.lead_sources import run_all_sources

HUB    = os.environ.get("HUB_URL", "http://10.118.155.218:8081")
FB     = Path("/root/feedback")
LOG    = FB / "data_acq_log.jsonl"
INTERVAL = int(os.environ.get("INTERVAL_SEC", str(6 * 3600)))


def log(level, msg, **fields):
    e = {"ts": datetime.now(timezone.utc).isoformat(),
         "level": level, "msg": msg, **fields}
    FB.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(e) + "\n")
    print(json.dumps(e), flush=True)


def _hub_get(p, **k):
    try:
        return requests.get(f"{HUB}{p}", params=k, timeout=10).json()
    except Exception as e:
        log("ERROR", "hub_get", path=p, err=str(e)[:150])
        return {}


def hot_lanes() -> list:
    """Return (lane_key, heat) tuples sorted by heat desc."""
    subs = _hub_get("/v1/swarm/ledger")
    heat = subs.get("by_lane", {}) if isinstance(subs, dict) else {}
    return sorted(heat.items(), key=lambda kv: -kv[1])[:15]


def post(lead: dict, niche: str, metro: str, src: str) -> bool:
    body = {"niche": niche, "metro": metro,
            "source": f"acq_{src}",
            "name":   lead.get("name", ""),
            "phone":  lead.get("phone", ""),
            "email":  lead.get("email", ""),
            "address": lead.get("address", "")}
    try:
        r = requests.post(f"{HUB}/v1/leads/direct",
                          json=body, timeout=8).json()
        return bool(r.get("ok"))
    except Exception:
        return False


def scrape_for_lane(lane_key: str) -> int:
    niche, metro = lane_key.split(":")
    n_posted = 0
    try:
        for lead in run_all_sources(metro_filter=metro):
            if post(lead, niche, metro, "real"):
                n_posted += 1
                if n_posted >= 10:  # cap per-lane to avoid DB thrash
                    break
    except Exception as e:
        log("ERROR", "scrape", lane=lane_key, err=str(e)[:150])
    return n_posted


def cycle():
    lane_heap = hot_lanes()
    log("CYCLE_START", "data-acq cycle",
        hot_lane_count=len(lane_heap))
    total = 0
    for lane_key, heat in lane_heap:
        n = scrape_for_lane(lane_key)
        total += n
        log("EVENT", "lane_scraped", lane=lane_key, heat=heat, posted=n)
    log("CYCLE_END", "data-acq cycle",
        lanes_scanned=len(lane_heap), leads_posted=total)


if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] data-acq starting — {INTERVAL}s",
          flush=True)
    # first cycle after 60s grace
    time.sleep(60)
    while True:
        try:
            cycle()
        except Exception as e:
            log("ERROR", "cycle", err=str(e)[:200])
        time.sleep(INTERVAL)
