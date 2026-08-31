#!/usr/bin/env python3
"""market_cycle_all_niches.py — all-niche autonomous market sweep.

Runs one batch of the full niche universe per invocation, rotating so every
niche is covered on a rolling cadence. Designed to be driven by a cron job
(e.g. every 30m) so the entire niche list is swept continuously without a
single blocking multi-hour run.

State persisted in Redis (empire-net) so the rotation pointer survives
restarts. Each run sweeps BATCH niches x TOP_METROS metros.

Revenue path: SERP sweep -> waterfall enrich -> A2A marketplace -> Brevo/ads.
"""
import os
import sys
import json
import redis
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB = "/root/empire_os/empire_os.db"
BATCH = int(os.environ.get("SWEEP_BATCH", 20))
TOP_METROS = (os.environ.get("SWEEP_METROS", "").split(",")
              if os.environ.get("SWEEP_METROS") else None)
LIMIT = int(os.environ.get("SWEEP_LIMIT", 3))

r = redis.Redis(host=os.environ.get("REDIS_HOST", "127.0.0.1"), port=6379, db=0)


def all_niches():
    c = sqlite3.connect(DB, timeout=30)
    c.execute("PRAGMA busy_timeout=30000")
    rows = [r[0] for r in c.execute(
        "SELECT DISTINCT niche FROM crm_leads WHERE niche IS NOT NULL AND niche != ''").fetchall()]
    c.close()
    return [n for n in rows if n and len(n) < 60]


def top_metros():
    if TOP_METROS:
        return TOP_METROS
    c = sqlite3.connect(DB, timeout=30)
    c.execute("PRAGMA busy_timeout=30000")
    rows = [r[0] for r in c.execute(
        "SELECT metro, COUNT(*) c FROM crm_leads WHERE metro IS NOT NULL AND metro != '' "
        "GROUP BY metro ORDER BY c DESC LIMIT 2").fetchall()]
    c.close()
    return rows or [""]


def main():
    # Slash per-niche search fan-out: general + hiring only (not all 5 intents),
    # so a batch of N niches stays bounded (<~3min) and the full universe rotates fast.
    import empire_os.lead_engine.serp_discovery as sd
    sd.INTENT = ["", "hiring"]

    niches = all_niches()
    if not niches:
        print("NO_NICHES")
        return
    metros = top_metros()

    # rotation pointer in redis
    idx = int(r.get("sweep:idx") or 0)
    chunk = niches[idx:idx + BATCH] or niches[:BATCH]
    next_idx = (idx + BATCH) % len(niches)
    r.set("sweep:idx", next_idx)
    r.set("sweep:last_run", json.dumps({"idx": idx, "niches": chunk, "metros": metros}))

    from empire_os.market_agent import run_market_cycle
    res = run_market_cycle(niches=chunk, metros=metros, limit=LIMIT)
    sweep = res.get("serp_sweep", {})
    print("SWEEP_BATCH",
          "batch_idx=" + str(idx),
          "batch_niches=" + str(len(chunk)),
          "total_niches=" + str(len(niches)),
          "swept_metros=" + str(sweep.get("swept_metros")),
          "added=" + str(sweep.get("total_added")),
          "enriched=" + str(res.get("enriched")),
          "wf_wins=" + str(res.get("waterfall_metrics", {}).get("successes")))


if __name__ == "__main__":
    main()
