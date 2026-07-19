#!/usr/bin/env python3
"""
marketing_strategies.py — orchestrates the unified intake + 3 marketing
strategies (rank / rent / rolling-stones) as one durable loop.

Order each tick:
  1. funnel_intake.seed_from_existing()  — keep si_intake_event fresh
  2. strategy_rank.compute()            — ROI board
  3. strategy_rent.run_rent()           — arbitrage (live per-lead billing)
  4. strategy_rolling_stones.run()      — volume yield report

Each module is independently runnable. This file just sequences them and
writes a consolidated snapshot to marketing_snapshot.json.
"""
from __future__ import annotations
import json, os, sys, time
from datetime import datetime, timezone

sys.path.insert(0, "/root/empire_os")
import empire_os.agents.funnel_intake as FI
import empire_os.agents.strategy_rank as SR
import empire_os.agents.strategy_rent as RENT
import empire_os.agents.strategy_rolling_stones as RS

SNAP = os.environ.get("MARKETING_SNAP", "/root/empire_os/marketing_snapshot.json")
TICK = int(os.environ.get("MARKETING_TICK", "900"))  # 15 min


def tick(dry_run: bool = False) -> dict:
    snap = {"ts": datetime.now(timezone.utc).isoformat(), "dry_run": dry_run}
    snap["intake"] = FI.seed_from_existing()
    snap["funnel_counts"] = FI.funnel_counts()
    snap["rank"] = SR.compute()[:10]
    snap["rent"] = RENT.run_rent(dry_run=dry_run, max_leads=150)
    snap["rolling_stones"] = RS.run(dry_run=dry_run, max_per_funnel=400)
    with open(SNAP, "w") as f:
        json.dump(snap, f, indent=2, default=str)
    return snap


def main():
    dry = os.environ.get("DRY_RUN", "0") == "1"
    print(f"📣 marketing_strategies orchestrator (dry={dry})")
    while True:
        try:
            s = tick(dry_run=dry)
            print(f"[{s['ts']}] intake={s['intake']} rank={len(s['rank'])} "
                  f"rent_billed={s['rent']['billed']} "
                  f"rs_yieldx={s['rolling_stones'].get('yield_multiple_vs_ideal')}")
        except Exception as e:
            print(f"tick error: {e}")
        time.sleep(TICK)


if __name__ == "__main__":
    main()
